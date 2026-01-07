import sys
import os
import json
import time
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QSlider, QDoubleSpinBox,
                             QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
                             QProgressBar, QFrame, QGridLayout, QScrollArea, QGroupBox,
                             QMessageBox, QFileDialog)
from PyQt5.QtGui import QPalette, QColor, QFont, QPixmap, QImage
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
import vlc
from dask.distributed import Client, LocalCluster, as_completed
import imageio.v3 as iio
import socket
import dask

# Configuración Dask
dask.config.set({
    "distributed.comm.timeouts.connect": "60s",
    "distributed.comm.timeouts.tcp": "60s",
    "distributed.worker.profile.interval": "2000ms",
})

# Importar sistema de persistencia
# NOTA: Asegúrate de tener los archivos en la carpeta 'utils'
from utils.database import RenderDatabase
from utils.progress_tracker import ProgressTracker, RecoveryManager


class RenderThread(QThread):
    """Thread para ejecutar el renderizado sin bloquear la GUI"""
    log_message = pyqtSignal(str)
    worker_update = pyqtSignal(dict)
    frame_completed = pyqtSignal(int, bytes)
    render_finished = pyqtSignal(float)
    render_error = pyqtSignal(str)
    
    def __init__(self, config, client, db, render_id, tracker):
        super().__init__()
        self.config = config
        self.client = client
        self.db = db
        self.render_id = render_id
        self.tracker = tracker
        self.running = True
    
    def run(self):
        """Ejecutar renderizado"""
        try:
            from tareas import generar_frame_mandelbrot
            
            total_frames = self.config['total_frames']
            start_time = time.time()
            
            self.log_message.emit(f"Iniciando renderizado de {total_frames} frames...")
            
            # Preparar tareas
            lista_tareas = []
            for i in range(total_frames):
                t = i / (total_frames - 1) if total_frames > 1 else 0
                zoom_actual = self.config['zoom_inicial'] * (self.config['zoom_final'] / self.config['zoom_inicial']) ** t
                
                ancho = 3.5 / zoom_actual
                alto = 2.5 / zoom_actual
                
                params = {
                    'frame_num': i,
                    'width': self.config['width'],
                    'height': self.config['height'],
                    'max_iter': self.config['max_iter'],
                    'x_min': self.config['x_centro'] - ancho / 2,
                    'x_max': self.config['x_centro'] + ancho / 2,
                    'y_min': self.config['y_centro'] - alto / 2,
                    'y_max': self.config['y_centro'] + alto / 2
                }
                lista_tareas.append(params)
            
            # Registrar workers conectados al inicio
            workers_info = self.client.scheduler_info()['workers']
            for worker_addr, worker_info in workers_info.items():
                worker_name = worker_info.get('name', 'Unknown')
                worker_ip = worker_addr.split('://')[1].split(':')[0] if '://' in worker_addr else 'unknown'
                self.db.add_worker(self.render_id, worker_name, worker_ip)
                self.log_message.emit(f"Worker registrado: {worker_name} ({worker_ip})")
            
            # Enviar tareas al cluster
            futures = self.client.map(generar_frame_mandelbrot, lista_tareas)
            self.log_message.emit(f"Tareas enviadas. Recibiendo resultados...")
            
            frames_guardados = 0
            frames_fallidos = 0
            completed_frames = set()
            failed_frames = set()
            pending_frames = set(range(total_frames))
            
            # Recibir resultados con timeout
            for future in as_completed(futures):
                if not self.running:
                    break
                
                try:
                    # Timeout de 5 minutos por frame
                    num_frame, img_bytes = future.result(timeout=300)
                    
                    # Obtener worker que completó el frame
                    worker_name =  None
                    try:
                        # Intentar obtener info del future
                        if hasattr(future, 'key'):
                            task_info = self.client.who_has(future.key)
                            if task_info and future.key in task_info:
                                worker_addrs = task_info[future.key]
                                if worker_addrs:
                                    # Obtener nombre del worker
                                    workers_info = self.client.scheduler_info()['workers']
                                    for addr in worker_addrs:
                                        if addr in workers_info:
                                            worker_name = workers_info[addr].get('name', None)
                                            break
                    except:
                        pass
                    
                    # Actualizar estado en DB
                    self.db.update_frame(self.render_id, num_frame, 'rendering', worker_name=worker_name)
                    
                    # Descomprimir si es necesario
                    # Verificar si está comprimido (no empieza con PNG magic number)
                    if not img_bytes.startswith(b'\x89PNG'):
                        try:
                            import zlib
                            img_bytes = zlib.decompress(img_bytes)
                            self.log_message.emit(f"Frame {num_frame} descomprimido")
                        except Exception as e:
                            self.log_message.emit(f"ERROR descomprimiendo frame {num_frame}: {e}")
                            continue
                    
                    # Guardar frame
                    os.makedirs(self.config['output_dir'], exist_ok=True)
                    nombre_archivo = f"frame_{num_frame:04d}.png"
                    ruta_completa = os.path.join(self.config['output_dir'], nombre_archivo)
                    
                    with open(ruta_completa, "wb") as f:
                        f.write(img_bytes)
                    
                    file_size = len(img_bytes)
                    frames_guardados += 1
                    
                    # Actualizar en base de datos
                    self.db.update_frame(
                        self.render_id, num_frame, 'completed',
                        render_time=time.time() - start_time,
                        file_path=ruta_completa,
                        file_size=file_size
                    )
                    
                    # Actualizar tracker de progreso
                    completed_frames.add(num_frame)
                    pending_frames.discard(num_frame)
                    self.tracker.save_progress(completed_frames, failed_frames, pending_frames)
                    
                    # Emitir señal de frame completado
                    self.frame_completed.emit(num_frame, img_bytes)
                    
                    porcentaje = int((frames_guardados / total_frames) * 100)
                    self.log_message.emit(f"[{porcentaje}%] Frame {num_frame} guardado")
                    
                except TimeoutError:
                    frames_fallidos += 1
                    failed_frames.add(num_frame)
                    pending_frames.discard(num_frame)
                    self.db.update_frame(self.render_id, num_frame, 'failed', error_message='Timeout (300s)')
                    self.tracker.save_progress(completed_frames, failed_frames, pending_frames)
                    self.log_message.emit(f"TIMEOUT: Frame {num_frame} tardó más de 5 minutos")
                    
                except Exception as e:
                    frames_fallidos += 1
                    failed_frames.add(num_frame)
                    pending_frames.discard(num_frame)
                    self.db.update_frame(self.render_id, num_frame, 'failed', error_message=str(e))
                    self.tracker.save_progress(completed_frames, failed_frames, pending_frames)
                    self.log_message.emit(f"ERROR en frame {num_frame}: {str(e)}")
            
            tiempo_render = time.time() - start_time
            
            # Verificar completitud
            if frames_fallidos > 0:
                self.log_message.emit(f"⚠️ RENDERIZADO INCOMPLETO: {frames_fallidos} frames fallidos")
                self.db.update_render_status(self.render_id, 'failed')
            else:
                self.log_message.emit(f"Renderizado completo en {tiempo_render:.2f}s")
                self.db.complete_render(self.render_id, tiempo_render)
                self.tracker.clear()
            
            self.render_finished.emit(tiempo_render)
            
        except Exception as e:
            self.render_error.emit(str(e))
    
    def stop(self):
        """Detener renderizado"""
        self.running = False


class MasterWindow(QMainWindow):
    """Ventana principal del Master con configuración y monitoreo"""
    
    def __init__(self):
        super().__init__()
        self.cluster = None
        self.client = None
        self.render_thread = None
        self.frames_data = {}
        self.db = RenderDatabase()  # Inicializar base de datos
        self.render_id = None
        self.tracker = None
        self.load_presets()
        
        self.init_ui()
        self.apply_dark_theme()
        self.start_cluster()
        self.start_monitoring()
        
        # Verificar recovery al iniciar
        self.check_recovery()
    
    def load_presets(self):
        """Cargar presets desde archivo JSON"""
        try:
            preset_path = os.path.join(os.path.dirname(__file__), 'config', 'presets.json')
            with open(preset_path, 'r') as f:
                self.presets = json.load(f)
        except Exception as e:
            print(f"Error cargando presets: {e}")
            self.presets = {}
    
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        self.setWindowTitle("Dask Master - Mandelbrot Cluster Control")
        self.setGeometry(50, 50, 1200, 800)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Tab 1: Configuración
        self.config_tab = self.create_config_tab()
        self.tabs.addTab(self.config_tab, "Configuracion")
        
        # Tab 2: Dashboard
        self.dashboard_tab = self.create_dashboard_tab()
        self.tabs.addTab(self.dashboard_tab, "Cluster Dashboard")
        
        # Tab 3: Galería
        self.gallery_tab = self.create_gallery_tab()
        self.tabs.addTab(self.gallery_tab, "Galeria de Frames")
        
        # Status Bar
        self.statusBar().showMessage("Iniciando cluster...")
    
    def create_config_tab(self):
        """Crear pestaña de configuración"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Preset Selector
        preset_group = QGroupBox("Preset de Configuracion")
        preset_layout = QVBoxLayout()
        
        self.preset_combo = QComboBox()
        for key, preset in self.presets.items():
            self.preset_combo.addItem(preset['name'], key)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        preset_layout.addWidget(self.preset_combo)
        
        self.preset_desc_label = QLabel("")
        self.preset_desc_label.setStyleSheet("color: #b0b0b0; font-style: italic;")
        preset_layout.addWidget(self.preset_desc_label)
        
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        # Resolution Group
        res_group = QGroupBox("Resolucion")
        res_layout = QGridLayout()
        
        res_layout.addWidget(QLabel("Ancho:"), 0, 0)
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(400, 3840)
        self.width_slider.setValue(800)
        self.width_slider.valueChanged.connect(self.update_width_label)
        res_layout.addWidget(self.width_slider, 0, 1)
        self.width_label = QLabel("800 px")
        res_layout.addWidget(self.width_label, 0, 2)
        
        res_layout.addWidget(QLabel("Alto:"), 1, 0)
        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(300, 2160)
        self.height_slider.setValue(608)
        self.height_slider.valueChanged.connect(self.update_height_label)
        res_layout.addWidget(self.height_slider, 1, 1)
        self.height_label = QLabel("608 px")
        res_layout.addWidget(self.height_label, 1, 2)
        
        res_group.setLayout(res_layout)
        layout.addWidget(res_group)
        
        # Animation Group
        anim_group = QGroupBox("Animacion")
        anim_layout = QGridLayout()
        
        anim_layout.addWidget(QLabel("Total Frames:"), 0, 0)
        self.frames_slider = QSlider(Qt.Horizontal)
        self.frames_slider.setRange(10, 200)
        self.frames_slider.setValue(50)
        self.frames_slider.valueChanged.connect(self.update_frames_label)
        anim_layout.addWidget(self.frames_slider, 0, 1)
        self.frames_label = QLabel("50")
        anim_layout.addWidget(self.frames_label, 0, 2)
        
        anim_layout.addWidget(QLabel("Max Iteraciones:"), 1, 0)
        self.iter_slider = QSlider(Qt.Horizontal)
        self.iter_slider.setRange(50, 500)
        self.iter_slider.setValue(100)
        self.iter_slider.valueChanged.connect(self.update_iter_label)
        anim_layout.addWidget(self.iter_slider, 1, 1)
        self.iter_label = QLabel("100")
        anim_layout.addWidget(self.iter_label, 1, 2)
        
        anim_layout.addWidget(QLabel("Zoom Final:"), 2, 0)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(100, 50000)
        self.zoom_slider.setValue(15000)
        self.zoom_slider.valueChanged.connect(self.update_zoom_label)
        anim_layout.addWidget(self.zoom_slider, 2, 1)
        self.zoom_label = QLabel("15000x")
        anim_layout.addWidget(self.zoom_label, 2, 2)
        
        anim_group.setLayout(anim_layout)
        layout.addWidget(anim_group)
        
        # Coordinates Group
        coord_group = QGroupBox("Coordenadas del Centro")
        coord_layout = QHBoxLayout()
        
        coord_layout.addWidget(QLabel("X:"))
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-2.0, 1.0)
        self.x_spin.setValue(-0.7436438870371587)
        self.x_spin.setDecimals(16)
        self.x_spin.setSingleStep(0.01)
        coord_layout.addWidget(self.x_spin)
        
        coord_layout.addWidget(QLabel("Y:"))
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-1.5, 1.5)
        self.y_spin.setValue(0.1318259042053119)
        self.y_spin.setDecimals(16)
        self.y_spin.setSingleStep(0.01)
        coord_layout.addWidget(self.y_spin)
        
        coord_group.setLayout(coord_layout)
        layout.addWidget(coord_group)
        
        layout.addStretch()
        
        # Start Button
        self.start_button = QPushButton("Iniciar Renderizado")
        self.start_button.setMinimumHeight(50)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
        """)
        self.start_button.clicked.connect(self.start_rendering)
        layout.addWidget(self.start_button)
        
        # Cargar primer preset
        self.on_preset_changed(0)
        
        return tab
    
    def create_dashboard_tab(self):
        """Crear pestaña de dashboard"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Workers Table
        workers_group = QGroupBox("Workers Conectados")
        workers_layout = QVBoxLayout()

        # Header con botón refresh
        header_layout = QHBoxLayout()
        self.refresh_button = QPushButton("🔄 Refresh Workers")
        self.refresh_button.setFixedWidth(180)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        self.refresh_button.clicked.connect(lambda: self.refresh_workers())
        header_layout.addWidget(self.refresh_button)
        header_layout.addStretch()
        workers_layout.addLayout(header_layout)
        
        self.workers_table = QTableWidget()
        self.workers_table.setColumnCount(9)
        self.workers_table.setHorizontalHeaderLabels([
            "Worker Name", 
            "IP", 
            "Status", 
            "Current Frame",
            "Lines",
            "Progress",
            "Speed",
            "Frames Done",
            "Memory"
        ])
        self.workers_table.horizontalHeader().setStretchLastSection(True)
        self.workers_table.setRowHeight(0, 60)  # Altura para mini-previews
        workers_layout.addWidget(self.workers_table)
        
        # Tracking de estadísticas por worker
        self.worker_stats = {}  # {worker_name: {frames: int, start_time: float}}
        
        workers_group.setLayout(workers_layout)
        layout.addWidget(workers_group)
        
        # Progress
        progress_group = QGroupBox("Progreso de Renderizado")
        progress_layout = QVBoxLayout()
        
        self.global_progress = QProgressBar()
        self.global_progress.setMinimumHeight(30)
        progress_layout.addWidget(self.global_progress)
        
        self.progress_label = QLabel("Esperando inicio de renderizado...")
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Log Viewer
        log_group = QGroupBox("Log de Eventos")
        log_layout = QVBoxLayout()
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumHeight(200)
        log_layout.addWidget(self.log_viewer)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        return tab
    
    def create_gallery_tab(self):
        """Crear pestaña de galería"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Scroll Area para miniaturas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.gallery_layout = QGridLayout(scroll_widget)
        scroll.setWidget(scroll_widget)
        
        layout.addWidget(QLabel("Frames Completados:"))
        layout.addWidget(scroll)
        
        # Video Controls
        video_group = QGroupBox("Generacion de Video")
        video_layout = QVBoxLayout()
        
        # Player Area
        player_layout = QHBoxLayout()
        
        self.video_frame = QFrame()
        self.video_frame.setMinimumHeight(400)
        self.video_frame.setStyleSheet("background-color: black;")
        player_layout.addWidget(self.video_frame)
        
        video_layout.addLayout(player_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.generate_video_button = QPushButton("Generar Video MP4")
        self.generate_video_button.clicked.connect(self.generate_video)
        self.generate_video_button.setEnabled(False)
        controls_layout.addWidget(self.generate_video_button)
        
        self.play_button = QPushButton("Reproducir")
        self.play_button.clicked.connect(self.play_video)
        self.play_button.setEnabled(False)
        controls_layout.addWidget(self.play_button)
        
        self.stop_button = QPushButton("Detener")
        self.stop_button.clicked.connect(self.stop_video)
        self.stop_button.setEnabled(False)
        controls_layout.addWidget(self.stop_button)
        
        video_layout.addLayout(controls_layout)
        
        video_group.setLayout(video_layout)
        layout.addWidget(video_group)
        
        # VLC Player Init
        self.vlc_instance = vlc.Instance()
        self.media_player = self.vlc_instance.media_player_new()
        self.current_video_path = None
        
        return tab
    
    def apply_dark_theme(self):
        """Aplicar tema oscuro"""
        app = QApplication.instance()
        app.setStyle("Fusion")
        
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(43, 43, 43))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(0, 212, 255))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        
        app.setPalette(palette)
    
    def start_cluster(self):
        """Iniciar cluster Dask"""
        try:
            ip = self.get_local_ip()
            self.cluster = LocalCluster(
                host='0.0.0.0',
                scheduler_port=8786,
                n_workers=0,
                dashboard_address=':8787'
            )
            self.client = Client(self.cluster)
            
            self.log(f"Cluster iniciado en {ip}:8786")
            self.log(f"Dashboard disponible en http://{ip}:8787")
            self.statusBar().showMessage(f"Cluster activo - Dashboard: http://{ip}:8787")
            
        except Exception as e:
            self.log(f"ERROR iniciando cluster: {str(e)}")
            QMessageBox.critical(self, "Error", f"No se pudo iniciar el cluster:\n{str(e)}")
    
    def start_monitoring(self):
        """Iniciar monitoreo de workers"""
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.update_workers_table)
        self.monitor_timer.start(500)  # Actualizar cada 500ms para visualización más fluida
    
    def update_workers_table(self):
        """Actualizar tabla de workers"""
        if not self.client:
            return
        
        try:
            from dask.distributed import Variable
            
            workers = self.client.scheduler_info()['workers']
            self.workers_table.setRowCount(len(workers))
            
            for i, (addr, info) in enumerate(workers.items()):
                worker_name = info.get('name', 'Unknown')
                
                # Set row height for this row
                self.workers_table.setRowHeight(i, 50)
                
                # Name
                name_item = QTableWidgetItem(worker_name)
                self.workers_table.setItem(i, 0, name_item)
                
                # IP
                ip = addr.split('://')[1].split(':')[0] if '://' in addr else addr
                ip_item = QTableWidgetItem(ip)
                self.workers_table.setItem(i, 1, ip_item)
                
                # Intentar leer progreso del worker (SOLO si existe la variable)
                frame_num = '-'
                prog = 0
                status = ''
                lines_completed = 0
                total_lines = 0
                lines_per_sec = 0
                
                try:
                    # Usar timeout muy corto y no crear Variable si no existe
                    progress_var = Variable(f'{worker_name}_progress', client=self.client)
                    progress_data = progress_var.get(timeout=0.05)
                    
                    if progress_data:
                        frame_num = progress_data.get('frame_num', '-')
                        prog = progress_data.get('progress', 0)
                        status = progress_data.get('status', '')
                        lines_completed = progress_data.get('lines_completed', 0)
                        total_lines = progress_data.get('total_lines', 0)
                        lines_per_sec = progress_data.get('lines_per_sec', 0)
                        
                        # Actualizar contador de frames completados
                        if status == 'completed':
                            if worker_name not in self.worker_stats:
                                self.worker_stats[worker_name] = {'frames': 0, 'start_time': time.time()}
                            # Solo incrementar si es un frame nuevo
                            last_frame = self.worker_stats[worker_name].get('last_frame', -1)
                            if frame_num != last_frame:
                                self.worker_stats[worker_name]['frames'] += 1
                                self.worker_stats[worker_name]['last_frame'] = frame_num
                
                except:
                    # Variable no existe o timeout - worker no está renderizando
                    pass
                
                # Status con color
                if status == 'rendering':
                    status_item = QTableWidgetItem("Rendering")
                    status_item.setForeground(QColor(52, 152, 219))  # Azul
                elif status == 'completed':
                    status_item = QTableWidgetItem("Completed")
                    status_item.setForeground(QColor(46, 204, 113))  # Verde
                elif status == 'started':
                    status_item = QTableWidgetItem("Starting")
                    status_item.setForeground(QColor(241, 196, 15))  # Amarillo
                else:
                    status_item = QTableWidgetItem("Idle")
                    status_item.setForeground(QColor(127, 140, 141))  # Gris
                
                self.workers_table.setItem(i, 2, status_item)
                
                # Current Frame
                frame_item = QTableWidgetItem(f"#{frame_num}" if frame_num != '-' else '-')
                if status == 'rendering':
                    frame_item.setForeground(QColor(52, 152, 219))
                self.workers_table.setItem(i, 3, frame_item)
                
                # Lines (nueva columna)
                if total_lines > 0:
                    lines_text = f"{lines_completed}/{total_lines}"
                    lines_item = QTableWidgetItem(lines_text)
                    if status == 'rendering':
                        lines_item.setForeground(QColor(52, 152, 219))
                else:
                    lines_item = QTableWidgetItem("--/--")
                
                self.workers_table.setItem(i, 4, lines_item)
                
                # Progress con barra visual
                if status == 'rendering':
                    progress_item = QTableWidgetItem(f"{prog}%")
                    progress_item.setForeground(QColor(52, 152, 219))  # Azul
                elif status == 'completed':
                    progress_item = QTableWidgetItem("100%")
                    progress_item.setForeground(QColor(46, 204, 113))  # Verde
                else:
                    progress_item = QTableWidgetItem("--")
                
                self.workers_table.setItem(i, 5, progress_item)
                
                # Speed (nueva columna)
                if lines_per_sec > 0:
                    speed_item = QTableWidgetItem(f"{lines_per_sec:.1f} l/s")
                    speed_item.setForeground(QColor(0, 212, 255))  # Cyan
                else:
                    speed_item = QTableWidgetItem("-- l/s")
                
                self.workers_table.setItem(i, 6, speed_item)
                
                # Frames Done
                frames_done = self.worker_stats.get(worker_name, {}).get('frames', 0)
                frames_item = QTableWidgetItem(str(frames_done))
                self.workers_table.setItem(i, 7, frames_item)
                
                # Memory
                memory_mb = info.get('memory_limit', 0) / (1024 * 1024)
                memory_item = QTableWidgetItem(f"{memory_mb:.0f} MB")
                self.workers_table.setItem(i, 8, memory_item)
            
            # Actualizar botón de inicio
            self.start_button.setEnabled(len(workers) > 0 and not self.is_rendering())
            
        except Exception as e:
            # Silenciar errores de conexión
            pass
    
    def refresh_workers(self):
        """Refrescar manualmente la lista de workers."""
        try:
            self.log("🔄 Refrescando workers...")
            self.update_workers_table()
        
            # Contar workers
            if self.client:
                workers = self.client.scheduler_info()['workers']
                count = len(workers)
                self.log(f"{count} worker(s) detectado(s)")
            else:
                self.log("Cluster no iniciado")
                
        except Exception as e:
            self.log(f"Error refrescando: {str(e)}")
    
    
    def on_preset_changed(self, index):
        """Callback cuando cambia el preset"""
        preset_key = self.preset_combo.currentData()
        if preset_key and preset_key in self.presets:
            preset = self.presets[preset_key]
            
            # Actualizar descripción
            self.preset_desc_label.setText(preset['description'])
            
            # Actualizar controles
            self.width_slider.setValue(preset['width'])
            self.height_slider.setValue(preset['height'])
            self.frames_slider.setValue(preset['total_frames'])
            self.iter_slider.setValue(preset['max_iter'])
            self.zoom_slider.setValue(int(preset['zoom_final']))
            self.x_spin.setValue(preset['x_centro'])
            self.y_spin.setValue(preset['y_centro'])
            
            # Deshabilitar sliders si no es custom
            is_custom = preset_key == 'custom'
            self.width_slider.setEnabled(is_custom)
            self.height_slider.setEnabled(is_custom)
            self.frames_slider.setEnabled(is_custom)
            self.iter_slider.setEnabled(is_custom)
            self.zoom_slider.setEnabled(is_custom)
            self.x_spin.setEnabled(is_custom)
            self.y_spin.setEnabled(is_custom)
    
    def update_width_label(self, value):
        self.width_label.setText(f"{value} px")
    
    def update_height_label(self, value):
        self.height_label.setText(f"{value} px")
    
    def update_frames_label(self, value):
        self.frames_label.setText(str(value))
    
    def update_iter_label(self, value):
        self.iter_label.setText(str(value))
    
    def update_zoom_label(self, value):
        self.zoom_label.setText(f"{value}x")
    
    def check_recovery(self):
        """Verifica si hay renders pendientes de recuperar."""
        if not ProgressTracker.has_pending_recovery():
            return
        
        recovery_info = ProgressTracker.get_recovery_info()
        
        reply = QMessageBox.question(
            self,
            "Render Incompleto Detectado",
            f"¡Se encontró un render incompleto!\n\n"
            f"Render ID: {recovery_info['render_id']}\n"
            f"Completados: {recovery_info['completed_count']} frames\n"
            f"Pendientes: {recovery_info['pending_count']} frames\n"
            f"Iniciado: {recovery_info['started_at']}\n\n"
            f"¿Deseas recuperar y continuar este render?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Implementar recuperación automática
            self.log(f"Iniciando recuperación del Render #{recovery_info['render_id']}...")
            
            # Cargar progreso y preparar recovery
            render_id = recovery_info['render_id']
            tracker = ProgressTracker(render_id)
            progress = tracker.load_progress()
            
            # IMPORTANTE: Actualizar tracker.data con el progreso cargado
            if progress:
                tracker.data = progress
            
            # Usar RecoveryManager
            from utils.progress_tracker import RecoveryManager
            recovery_data = RecoveryManager.recover_render(self.db, tracker)
            
            if not recovery_data['can_resume']:
                QMessageBox.warning(
                    self,
                    "No se puede recuperar",
                    f"El render no tiene frames completados para recuperar."
                )
                tracker.clear()
                return
            
            # Obtener info del render desde DB
            render_info = self.db.get_render(render_id)
            if not render_info:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"No se encontró el Render #{render_id} en la base de datos."
                )
                tracker.clear()
                return
            
            # Configurar la GUI con los valores del render anterior
            self.width_slider.setValue(render_info['width'])
            self.height_slider.setValue(render_info['height'])
            self.frames_slider.setValue(render_info['total_frames'])
            self.iter_slider.setValue(render_info['max_iter'])
            
            # Parsear fractal_config
            import json as json_module
            fractal_config = json_module.loads(render_info['fractal_config']) if render_info['fractal_config'] else {}
            self.zoom_slider.setValue(int(fractal_config.get('zoom_final', 15000)))
            self.x_spin.setValue(fractal_config.get('x_centro', -0.7436))
            self.y_spin.setValue(fractal_config.get('y_centro', 0.1318))
            
            # Guardar render_id y tracker para continuar
            self.render_id = render_id
            self.tracker = tracker
            
            # Informar al usuario
            QMessageBox.information(
                self,
                "Recovery Preparado",
                f"Recovery configurado exitosamente.\n\n"
                f"La configuración ha sido cargada del render anterior.\n"
                f"Los controles están BLOQUEADOS para evitar cambios.\n\n"
                f"Solo se renderizarán los {len(recovery_data['frames_to_render'])} frames pendientes.\n"
                f"Esto ahorrará ~{recovery_data['estimated_time_saved']:.1f} segundos de trabajo."
            )
            
            # BLOQUEAR controles para evitar cambios
            self.preset_combo.setEnabled(False)
            self.width_slider.setEnabled(False)
            self.height_slider.setEnabled(False)
            self.frames_slider.setEnabled(False)
            self.iter_slider.setEnabled(False)
            self.zoom_slider.setEnabled(False)
            self.x_spin.setEnabled(False)
            self.y_spin.setEnabled(False)
            
            # Cambiar color de fondo para indicar modo recovery
            self.config_tab.setStyleSheet("background-color: #2a4a2a;")
            
            self.log(f"Recovery preparado: {recovery_info['completed_count']} frames ya completados")
            self.log(f"Quedan {len(recovery_data['frames_to_render'])} frames por renderizar")
            self.log("⚠️ MODO RECOVERY: Controles bloqueados")
        else:
            # Limpiar progreso
            tracker = ProgressTracker(recovery_info['render_id'])
            tracker.clear()
            self.log("Progreso anterior descartado")
    
    def start_rendering(self):
        """Iniciar renderizado"""
        if not self.client:
            QMessageBox.warning(self, "Error", "Cluster no iniciado")
            return
        
        workers = self.client.scheduler_info()['workers']
        if len(workers) == 0:
            QMessageBox.warning(self, "Sin Workers", "Necesitas al menos 1 worker conectado")
            return
        
        # Preparar configuración
        config = {
            'width': self.width_slider.value(),
            'height': self.height_slider.value(),
            'total_frames': self.frames_slider.value(),
            'max_iter': self.iter_slider.value(),
            'zoom_inicial': 1.0,
            'zoom_final': self.zoom_slider.value(),
            'x_centro': self.x_spin.value(),
            'y_centro': self.y_spin.value(),
            'output_dir': './frames_renderizados',
            'preset': self.preset_combo.currentData()
        }
        
        # Registrar render en base de datos
        self.render_id = self.db.start_render('mandelbrot', config)
        self.log(f"Render registrado con ID: {self.render_id}")
        
        # Inicializar tracker de progreso
        self.tracker = ProgressTracker(self.render_id)
        
        # Registrar frames en base de datos
        for i in range(config['total_frames']):
            self.db.add_frame(self.render_id, i, status='pending')
        
        # Limpiar galería anterior
        self.frames_data.clear()
        self.clear_gallery()
        
        # Iniciar thread de renderizado
        self.render_thread = RenderThread(config, self.client, self.db, self.render_id, self.tracker)
        self.render_thread.log_message.connect(self.log)
        self.render_thread.frame_completed.connect(self.on_frame_completed)
        self.render_thread.render_finished.connect(self.on_render_finished)
        self.render_thread.render_error.connect(self.on_render_error)
        self.render_thread.start()
        
        # Actualizar UI
        self.start_button.setEnabled(False)
        self.global_progress.setMaximum(config['total_frames'])
        self.global_progress.setValue(0)
        self.progress_label.setText("Renderizando...")
        self.tabs.setCurrentIndex(1)  # Cambiar a dashboard
    
    def on_frame_completed(self, frame_num, img_bytes):
        """Callback cuando se completa un frame"""
        self.frames_data[frame_num] = img_bytes
        self.global_progress.setValue(len(self.frames_data))
        
        total = self.frames_slider.value()
        self.progress_label.setText(f"Frames completados: {len(self.frames_data)}/{total}")
        
        # Agregar a galería
        self.add_frame_to_gallery(frame_num, img_bytes)
    
    def on_render_finished(self, time_seconds):
        """Callback cuando termina el renderizado"""
        self.log(f"RENDERIZADO COMPLETO en {time_seconds:.2f} segundos")
        self.start_button.setEnabled(True)
        self.generate_video_button.setEnabled(True)
        self.progress_label.setText(f"Completado en {time_seconds:.2f}s")
        
        QMessageBox.information(self, "Exito", f"Renderizado completado en {time_seconds:.2f}s")
    
    def on_render_error(self, error_msg):
        """Callback cuando hay error en renderizado"""
        self.log(f"ERROR: {error_msg}")
        self.start_button.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Error en renderizado:\n{error_msg}")
    
    def add_frame_to_gallery(self, frame_num, img_bytes):
        """Agregar frame a la galería"""
        try:
            # Validar que hay datos
            if not img_bytes or len(img_bytes) == 0:
                print(f"Warning: Frame {frame_num} tiene datos vacíos")
                return
            
            # Convertir bytes a QPixmap
            qimage = QImage.fromData(img_bytes)
            
            # Validar que la imagen se cargó correctamente
            if qimage.isNull():
                print(f"Warning: No se pudo cargar imagen para frame {frame_num}")
                return
            
            pixmap = QPixmap.fromImage(qimage)
            
            # Validar pixmap
            if pixmap.isNull():
                print(f"Warning: Pixmap nulo para frame {frame_num}")
                return
            
            # Crear thumbnail
            thumbnail = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Crear label
            label = QLabel()
            label.setPixmap(thumbnail)
            label.setFrameStyle(QFrame.StyledPanel)
            label.setToolTip(f"Frame {frame_num}")
            
            # Agregar a grid (5 columnas)
            row = frame_num // 5
            col = frame_num % 5
            self.gallery_layout.addWidget(label, row, col)
            
        except Exception as e:
            print(f"Error adding frame to gallery: {e}")
    
    def clear_gallery(self):
        """Limpiar galería"""
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def generate_video(self):
        """Generar video MP4"""
        try:
            output_dir = './frames_renderizados'
            video_path = './mandelbrot_zoom.mp4'
            total_frames = self.frames_slider.value()
            
            self.log("Generando video MP4...")
            
            # Usar imageio v3 API
            frames = []
            for i in range(total_frames):
                ruta = os.path.join(output_dir, f"frame_{i:04d}.png")
                if os.path.exists(ruta):
                    try:
                        # Leer con PIL explícitamente
                        from PIL import Image
                        img = Image.open(ruta)
                        frames.append(img)
                    except Exception as e:
                        self.log(f"WARNING: Error leyendo frame {i}: {e}")
                else:
                    self.log(f"WARNING: Falta frame {i}")
            
            if not frames:
                raise Exception("No hay frames para generar video")
            
            # Guardar video
            iio.imwrite(video_path, frames, fps=15, codec='libx264')
            
            self.log(f"Video generado: {os.path.abspath(video_path)}")
            QMessageBox.information(self, "Exito", f"Video generado:\n{os.path.abspath(video_path)}")
            
            # Auto-play
            self.play_button.setEnabled(True)
            self.load_and_play_video(os.path.abspath(video_path))
            
        except Exception as e:
            self.log(f"ERROR generando video: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error generando video:\n{str(e)}")

    def load_and_play_video(self, path):
        """Cargar y reproducir video"""
        try:
            self.current_video_path = path
            media = self.vlc_instance.media_new(path)
            self.media_player.set_media(media)
            
            # Configurar salida de video en Windows
            if sys.platform.startswith('win'):
                self.media_player.set_hwnd(int(self.video_frame.winId()))
            elif sys.platform == 'darwin':
                self.media_player.set_nsobject(int(self.video_frame.winId()))
            else:
                self.media_player.set_xwindow(int(self.video_frame.winId()))
            
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.media_player.play()
            self.play_button.setText("Pausa")
            self.log("Video cargado y reproduciendo")
            
        except Exception as e:
            self.log(f"Error cargando video: {str(e)}")
            QMessageBox.warning(self, "Error", f"No se pudo cargar el video:\n{str(e)}")

    def play_video(self):
        """Alternar reproducción"""
        if self.media_player.is_playing():
            self.media_player.pause()
            self.play_button.setText("Reproducir")
        else:
            self.media_player.play()
            self.play_button.setText("Pausa")

    def stop_video(self):
        """Detener video"""
        self.media_player.stop()
        self.play_button.setText("Reproducir")
    
    def log(self, message):
        """Agregar mensaje al log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_viewer.append(f"[{timestamp}] {message}")
    
    def is_rendering(self):
        """Verificar si está renderizando"""
        return self.render_thread is not None and self.render_thread.isRunning()
    
    def get_local_ip(self):
        """Obtener IP local"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        if self.render_thread and self.render_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Renderizado en progreso",
                "Hay un renderizado en progreso. Deseas cancelar y salir?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
            
            self.render_thread.stop()
            self.render_thread.wait()
        
        if self.client:
            self.client.close()
        if self.cluster:
            self.cluster.close()
        
        event.accept()


def main():
    """Punto de entrada principal"""
    app = QApplication(sys.argv)
    window = MasterWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()