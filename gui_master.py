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
import imageio.v2 as imageio
import socket
import dask

# Configuración Dask
dask.config.set({
    "distributed.comm.timeouts.connect": "60s",
    "distributed.comm.timeouts.tcp": "60s",
    "distributed.worker.profile.interval": "2000ms",
})


class RenderThread(QThread):
    """Thread para ejecutar el renderizado sin bloquear la GUI"""
    log_message = pyqtSignal(str)
    worker_update = pyqtSignal(dict)
    frame_completed = pyqtSignal(int, bytes)
    render_finished = pyqtSignal(float)
    render_error = pyqtSignal(str)
    
    def __init__(self, config, client):
        super().__init__()
        self.config = config
        self.client = client
        self.running = True
    
    def run(self):
        """Ejecutar renderizado"""
        try:
            from tareas import generar_frame_mandelbrot
            
            total_frames = self.config['total_frames']
            start_time = time.time()
            
            self.log_message.emit(f"Iniciando renderizado de {total_frames} frames...")
            
            # Preparar lista de tareas
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
            
            # Enviar tareas al cluster
            futures = self.client.map(generar_frame_mandelbrot, lista_tareas)
            self.log_message.emit(f"Tareas enviadas. Recibiendo resultados...")
            
            frames_guardados = 0
            
            # Recibir resultados
            for future in as_completed(futures):
                if not self.running:
                    break
                
                try:
                    num_frame, img_bytes = future.result()
                    
                    # Guardar frame
                    os.makedirs(self.config['output_dir'], exist_ok=True)
                    nombre_archivo = f"frame_{num_frame:04d}.png"
                    ruta_completa = os.path.join(self.config['output_dir'], nombre_archivo)
                    
                    with open(ruta_completa, "wb") as f:
                        f.write(img_bytes)
                    
                    frames_guardados += 1
                    
                    # Emitir señal de frame completado
                    self.frame_completed.emit(num_frame, img_bytes)
                    
                    porcentaje = int((frames_guardados / total_frames) * 100)
                    self.log_message.emit(f"[{porcentaje}%] Frame {num_frame} guardado")
                    
                except Exception as e:
                    self.log_message.emit(f"ERROR en frame: {str(e)}")
            
            tiempo_render = time.time() - start_time
            self.log_message.emit(f"Renderizado completo en {tiempo_render:.2f}s")
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
        self.load_presets()
        
        self.init_ui()
        self.apply_dark_theme()
        self.start_cluster()
        self.start_monitoring()
    
    def load_presets(self):
        """Cargar presets desde archivo JSON"""
        try:
            preset_path = os.path.join(os.path.dirname(__file__), 'presets.json')
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
        
        self.workers_table = QTableWidget()
        self.workers_table.setColumnCount(5)
        self.workers_table.setHorizontalHeaderLabels(["Worker Name", "IP", "Status", "Threads", "Memory"])
        self.workers_table.horizontalHeader().setStretchLastSection(True)
        workers_layout.addWidget(self.workers_table)
        
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
        self.monitor_timer.start(1000)
    
    def update_workers_table(self):
        """Actualizar tabla de workers"""
        if not self.client:
            return
        
        try:
            workers = self.client.scheduler_info()['workers']
            self.workers_table.setRowCount(len(workers))
            
            for i, (addr, info) in enumerate(workers.items()):
                # Name
                name_item = QTableWidgetItem(info.get('name', 'Unknown'))
                self.workers_table.setItem(i, 0, name_item)
                
                # IP
                ip = addr.split('://')[1].split(':')[0] if '://' in addr else addr
                ip_item = QTableWidgetItem(ip)
                self.workers_table.setItem(i, 1, ip_item)
                
                # Status
                status_item = QTableWidgetItem("Activo")
                status_item.setForeground(QColor(46, 204, 113))
                self.workers_table.setItem(i, 2, status_item)
                
                # Threads
                threads_item = QTableWidgetItem(str(info.get('nthreads', 0)))
                self.workers_table.setItem(i, 3, threads_item)
                
                # Memory
                memory_mb = info.get('memory_limit', 0) / (1024 * 1024)
                memory_item = QTableWidgetItem(f"{memory_mb:.0f} MB")
                self.workers_table.setItem(i, 4, memory_item)
            
            # Actualizar botón de inicio
            self.start_button.setEnabled(len(workers) > 0 and not self.is_rendering())
            
        except Exception as e:
            print(f"Error updating workers: {e}")
    
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
            'output_dir': './frames_renderizados'
        }
        
        # Limpiar galería anterior
        self.frames_data.clear()
        self.clear_gallery()
        
        # Iniciar thread de renderizado
        self.render_thread = RenderThread(config, self.client)
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
            # Convertir bytes a QPixmap
            qimage = QImage.fromData(img_bytes)
            pixmap = QPixmap.fromImage(qimage)
            
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
            
            writer = imageio.get_writer(video_path, fps=15)
            
            for i in range(total_frames):
                ruta = os.path.join(output_dir, f"frame_{i:04d}.png")
                if os.path.exists(ruta):
                    img = imageio.imread(ruta)
                    writer.append_data(img)
                else:
                    self.log(f"WARNING: Falta frame {i}")
            
            writer.close()
            
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
