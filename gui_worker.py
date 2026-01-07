import sys
import io
import asyncio
import platform
import uuid
import time
import os
import re
from io import StringIO
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QProgressBar, QFrame, QListWidget,
                             QScrollArea, QGridLayout)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QPixmap, QImage, QPalette, QColor, QFont
from PIL import Image
from dask.distributed import Worker
import dask

# Configuración Robustez WiFi
dask.config.set({
    "distributed.comm.timeouts.connect": "45s",
    "distributed.comm.timeouts.tcp": "45s",
    # Aumentar tolerancia a latencia
    "distributed.comm.retry.count": 3,
})


class WorkerThread(QThread):
    """Thread para ejecutar el Dask Worker sin bloquear la GUI"""
    connection_status = pyqtSignal(bool, str)  # (connected, message)
    frame_started = pyqtSignal(int)  # frame_num
    frame_completed = pyqtSignal(int, float)  # frame_num, time_seconds
    task_info = pyqtSignal(str)  # info message
    
    def __init__(self, scheduler_ip, gui_window):
        super().__init__()
        self.scheduler_ip = scheduler_ip
        self.worker_name = f"Worker-{platform.node()}-{str(uuid.uuid4())[:4]}"
        self.running = True
        self.gui_window = gui_window
        self.current_frame = None
        self.frame_start_time = None
        self.stdout_buffer = None
    
    def run(self):
        """Ejecutar worker en thread separado"""
        # Crear buffer para capturar prints
        self.stdout_buffer = StringIO()
        original_stdout = sys.stdout
        
        # Wrapper para capturar y procesar prints
        class TeeOutput:
            def __init__(self, original, callback):
                self.original = original
                self.callback = callback
            
            def write(self, text):
                self.original.write(text)
                self.callback(text)
            
            def flush(self):
                self.original.flush()
        
        sys.stdout = TeeOutput(original_stdout, self.process_output)
        
        try:
            asyncio.run(self.start_worker())
        finally:
            sys.stdout = original_stdout
    
    def process_output(self, text):
        """Procesar output para detectar frames"""
        try:
            # Detectar inicio de frame: "Iniciando frame X"
            if "Iniciando frame" in text:
                match = re.search(r'Iniciando frame (\d+)', text)
                if match:
                    frame_num = int(match.group(1))
                    self.current_frame = frame_num
                    self.frame_start_time = time.time()
                    self.frame_started.emit(frame_num)
                    self.task_info.emit(f"Renderizando Frame {frame_num}...")
            
            # Detectar frame completado: "Frame X completado"
            elif "completado en" in text and "Frame" in text:
                match = re.search(r'Frame (\d+) completado en ([\d.]+)s', text)
                if match:
                    frame_num = int(match.group(1))
                    time_seconds = float(match.group(2))
                    self.frame_completed.emit(frame_num, time_seconds)
                    self.task_info.emit(f"Frame {frame_num} completado")
                    self.current_frame = None
                    self.frame_start_time = None
            
            # Detectar caché: "Frame X obtenido del caché"
            elif "obtenido del caché" in text:
                match = re.search(r'Frame (\d+) obtenido del caché', text)
                if match:
                    frame_num = int(match.group(1))
                    # Simular completado instantáneo
                    self.frame_completed.emit(frame_num, 0.01)
                    self.task_info.emit(f"Frame {frame_num} (caché)")
                    
        except Exception as e:
            print(f"Error processing output: {e}")
    
    async def start_worker(self):
        """Iniciar worker con reconexión automática"""
        direccion_master = f"tcp://{self.scheduler_ip}:8786"
        
        reconn_attempt = 0
        while self.running:
            worker = None
            try:
                reconn_attempt += 1
                self.connection_status.emit(False, f"Conectando... (intento #{reconn_attempt})")
                
                # CORRECCIÓN 1: Eliminado 'reconnect=False' (deprecated)
                # Dask moderno maneja esto mejor internamente o con Nanny, 
                # pero Worker() directo es suficiente aquí.
                worker = Worker(direccion_master, name=self.worker_name)
                
                # Iniciar worker
                await worker.start() # No usar wait_for aquí, start() suele ser rápido
                
                # Worker iniciado correctamente
                reconn_attempt = 0
                self.connection_status.emit(True, f"Conectado a {self.scheduler_ip}")
                
                # CORRECCIÓN 2: Usar wait() o finished() en lugar de bucle manual
                # Esto bloquea la ejecución aquí hasta que el worker muera
                await worker.finished()
                
                # Si llegamos aquí, el worker se cerró
                if self.running:
                    raise ConnectionError("Worker desconectado del scheduler")
                    
            except (OSError, ConnectionError) as e:
                self.connection_status.emit(False, f"Desconectado. Reintentando en 5s...")
                if worker:
                    try:
                        await worker.close()
                    except:
                        pass
                await asyncio.sleep(5)
                
            except Exception as e:
                error_msg = str(e)[:40]
                self.connection_status.emit(False, f"Error: {error_msg}. Reintentando...")
                if worker:
                    try:
                        await worker.close()
                    except:
                        pass
                await asyncio.sleep(5)

class WorkerWindow(QMainWindow):
    """Ventana principal del Worker con preview en tiempo real"""
    
    def __init__(self, scheduler_ip):
        super().__init__()
        self.scheduler_ip = scheduler_ip
        self.current_frame = None
        self.frames_completed = 0
        self.total_data_sent = 0
        self.frame_history = []
        self.worker_thread = None
        
        # Crear directorio para frames del worker
        self.worker_frames_dir = './worker_frames'
        os.makedirs(self.worker_frames_dir, exist_ok=True)
        
        self.init_ui()
        self.apply_dark_theme()
        self.start_worker_thread()
    
    def init_ui(self):
        """Inicializar interfaz de usuario"""
        self.setWindowTitle("Dask Worker - Mandelbrot Renderer")
        self.setGeometry(100, 100, 700, 550)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header Panel
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.StyledPanel)
        header_layout = QHBoxLayout(header_frame)
        
        self.status_led = QLabel("●")
        self.status_led.setStyleSheet("color: #e74c3c; font-size: 20px;")
        header_layout.addWidget(self.status_led)
        
        self.connection_label = QLabel("Desconectado")
        self.connection_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        header_layout.addWidget(self.connection_label)
        
        header_layout.addStretch()
        
        self.worker_name_label = QLabel("")
        self.worker_name_label.setFont(QFont("Segoe UI", 9))
        header_layout.addWidget(self.worker_name_label)
        
        main_layout.addWidget(header_frame)
        
        # Content Layout (Preview + Stats)
        content_layout = QHBoxLayout()
        
        # Preview Canvas (Left)
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.StyledPanel)
        preview_layout = QVBoxLayout(preview_frame)
        
        self.preview_label = QLabel("Esperando tareas del Master...")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(500, 380)
        self.preview_label.setStyleSheet("background-color: #2b2b2b; color: #b0b0b0;")
        self.preview_label.setScaledContents(False)
        preview_layout.addWidget(self.preview_label)
        
        content_layout.addWidget(preview_frame, 3)
        
        # Stats Panel (Right)
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_frame.setMaximumWidth(200)
        stats_layout = QVBoxLayout(stats_frame)
        
        # Current Frame
        stats_layout.addWidget(QLabel("Frame Actual:"))
        self.current_frame_label = QLabel("--")
        self.current_frame_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.current_frame_label.setStyleSheet("color: #00d4ff;")
        stats_layout.addWidget(self.current_frame_label)
        
        stats_layout.addSpacing(10)
        
        # Progress Bar (Vertical)
        stats_layout.addWidget(QLabel("Progreso:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setOrientation(Qt.Vertical)
        self.progress_bar.setMinimumHeight(150)
        self.progress_bar.setTextVisible(True)
        stats_layout.addWidget(self.progress_bar, alignment=Qt.AlignCenter)
        
        stats_layout.addSpacing(10)
        
        # Stats
        stats_layout.addWidget(QLabel("Completados:"))
        self.completed_label = QLabel("0 frames")
        stats_layout.addWidget(self.completed_label)
        
        stats_layout.addWidget(QLabel("Datos Enviados:"))
        self.data_sent_label = QLabel("0.0 MB")
        stats_layout.addWidget(self.data_sent_label)
        
        stats_layout.addStretch()
        
        content_layout.addWidget(stats_frame, 1)
        
        main_layout.addLayout(content_layout)
        
        # Gallery Section (Below preview)
        gallery_frame = QFrame()
        gallery_frame.setFrameStyle(QFrame.StyledPanel)
        gallery_layout = QVBoxLayout(gallery_frame)
        
        gallery_label = QLabel("Galería de Frames Completados")
        gallery_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        gallery_layout.addWidget(gallery_label)
        
        # Scroll area para galería
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(150)
        
        gallery_widget = QWidget()
        self.gallery_grid = QGridLayout(gallery_widget)
        self.gallery_grid.setSpacing(5)
        scroll.setWidget(gallery_widget)
        
        gallery_layout.addWidget(scroll)
        main_layout.addWidget(gallery_frame)
        
        # Tracking de frames completados
        self.completed_frames = []  # Lista de (frame_num, pixmap)
        
        # Footer Panel
        footer_frame = QFrame()
        footer_frame.setFrameStyle(QFrame.StyledPanel)
        footer_layout = QVBoxLayout(footer_frame)
        
        self.status_label = QLabel("Esperando conexión...")
        self.status_label.setFont(QFont("Segoe UI", 9))
        footer_layout.addWidget(self.status_label)
        
        # Line counter and speed
        stats_row = QHBoxLayout()
        self.line_counter_label = QLabel("Líneas: --/--")
        self.line_counter_label.setFont(QFont("Segoe UI", 8))
        stats_row.addWidget(self.line_counter_label)
        
        stats_row.addStretch()
        
        self.speed_label = QLabel("Velocidad: -- l/s")
        self.speed_label.setFont(QFont("Segoe UI", 8))
        self.speed_label.setStyleSheet("color: #00d4ff;")
        stats_row.addWidget(self.speed_label)
        
        footer_layout.addLayout(stats_row)
        
        self.footer_progress = QProgressBar()
        self.footer_progress.setMaximum(100)
        footer_layout.addWidget(self.footer_progress)
        
        main_layout.addWidget(footer_frame)
    
    def apply_dark_theme(self):
        """Aplicar tema oscuro a la aplicación"""
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
        
        self.setPalette(palette)
    
    def start_worker_thread(self):
        """Iniciar thread del worker"""
        self.worker_thread = WorkerThread(self.scheduler_ip, self)
        self.worker_thread.connection_status.connect(self.on_connection_status)
        self.worker_thread.frame_started.connect(self.on_frame_started)
        self.worker_thread.frame_completed.connect(self.on_frame_completed)
        self.worker_thread.task_info.connect(self.on_task_info)
        self.worker_thread.start()
        
        # Timer para animar LED
        self.led_timer = QTimer()
        self.led_timer.timeout.connect(self.animate_led)
        self.led_timer.start(1000)
        self.led_state = False
        
        # Timer para simular progreso mientras renderiza
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_simulated_progress)
        self.progress_value = 0
        
        # Timer para actualizar preview desde Dask (no bloqueante)
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview_from_dask)
        self.preview_timer.start(200)  # Actualizar cada 200ms para visualización fluida
        self.last_preview_frame = None
    
    def update_preview_from_dask(self):
        """Actualizar preview leyendo desde archivo temporal."""
        if not hasattr(self, 'worker_thread') or not hasattr(self.worker_thread, 'worker_name'):
            return
        
        try:
            worker_name = self.worker_thread.worker_name
            
            # Leer preview desde archivo temporal
            preview_file = f'./temp_previews/{worker_name}_preview.png'
            metadata_file = f'./temp_previews/{worker_name}_metadata.json'
            
            if os.path.exists(preview_file) and os.path.exists(metadata_file):
                # Leer metadata
                import json
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    frame_num = metadata.get('frame_num', -1)
                    lines_completed = metadata.get('lines_completed', 0)
                    total_lines = metadata.get('total_lines', 0)
                    lines_per_sec = metadata.get('lines_per_sec', 0)
                    progress = metadata.get('progress', 0)
                    is_partial = metadata.get('is_partial', False)
                    
                    # Leer imagen
                    pixmap = QPixmap(preview_file)
                    if not pixmap.isNull():
                        # Actualizar preview
                        scaled_pixmap = pixmap.scaled(
                            self.preview_label.size(),
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation
                        )
                        self.preview_label.setPixmap(scaled_pixmap)
                        self.preview_label.setText("")
                        
                        # Actualizar metadata
                        if total_lines > 0:
                            self.line_counter_label.setText(f"Líneas: {lines_completed}/{total_lines}")
                        
                        if lines_per_sec > 0:
                            self.speed_label.setText(f"Velocidad: {lines_per_sec:.1f} l/s")
                        
                        if progress > 0:
                            self.progress_bar.setValue(progress)
                            self.footer_progress.setValue(progress)
                
                except:
                    pass
        except:
            pass
    
    def update_preview_signal(self, preview_bytes, lines_completed=0, total_lines=0, is_partial=False):
        """Actualizar preview en GUI thread."""
        try:
            qimage = QImage.fromData(preview_bytes)
            
            if not qimage.isNull():
                pixmap = QPixmap.fromImage(qimage)
                # Escalar para llenar el área de preview
                scaled_pixmap = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled_pixmap)
                self.preview_label.setText("")  # Limpiar texto
                
                # Actualizar contador de líneas si está disponible
                if total_lines > 0:
                    self.line_counter_label.setText(f"Líneas: {lines_completed}/{total_lines}")
        except:
            pass
    
    def update_progress_metadata(self, lines_completed, total_lines, lines_per_sec, progress):
        """Actualizar metadata de progreso en UI."""
        try:
            # Actualizar contador de líneas
            if total_lines > 0:
                self.line_counter_label.setText(f"Líneas: {lines_completed}/{total_lines}")
            
            # Actualizar velocidad
            if lines_per_sec > 0:
                self.speed_label.setText(f"Velocidad: {lines_per_sec:.1f} l/s")
            
            # Actualizar barra de progreso suavemente
            if progress > 0:
                self.progress_bar.setValue(progress)
                self.footer_progress.setValue(progress)
        except:
            pass
    
    def animate_led(self):
        """Animar LED de conexión"""
        if hasattr(self, 'is_connected') and self.is_connected:
            if self.led_state:
                self.status_led.setStyleSheet("color: #2ecc71; font-size: 20px;")
            else:
                self.status_led.setStyleSheet("color: #27ae60; font-size: 20px;")
            self.led_state = not self.led_state
    
    def on_connection_status(self, connected, message):
        """Actualizar estado de conexión"""
        self.is_connected = connected
        self.connection_label.setText(message)
        
        if connected:
            self.status_led.setStyleSheet("color: #2ecc71; font-size: 20px;")
            self.worker_name_label.setText(self.worker_thread.worker_name)
            self.status_label.setText("Conectado. Esperando tareas...")
        else:
            self.status_led.setStyleSheet("color: #e74c3c; font-size: 20px;")
            self.status_label.setText(message)
    
    def on_frame_started(self, frame_num):
        """Callback cuando inicia un frame"""
        self.current_frame = frame_num
        self.current_frame_label.setText(f"#{frame_num}")
        self.status_label.setText(f"Renderizando Frame {frame_num}...")
        self.progress_bar.setValue(0)
        self.footer_progress.setValue(0)
        self.progress_value = 0
        
        # Iniciar animación de progreso
        self.progress_timer.start(200)  # Actualizar cada 200ms
        
        # Cambiar preview a mensaje de renderizado
        self.preview_label.setText(f"Renderizando Frame {frame_num}...\n\nEl preview aparecerá al completar")
    
    def update_simulated_progress(self):
        """Actualizar progreso simulado mientras renderiza"""
        if self.progress_value < 95:
            # Incremento variable para simular progreso realista
            increment = 2 if self.progress_value < 50 else 1
            self.progress_value = min(95, self.progress_value + increment)
            self.progress_bar.setValue(self.progress_value)
            self.footer_progress.setValue(self.progress_value)
    
    def on_task_info(self, message):
        """Callback para información de tareas"""
        self.status_label.setText(message)
    
    def on_frame_completed(self, frame_num, time_seconds):
        """Callback cuando completa un frame"""
        self.frames_completed += 1
        self.progress_timer.stop()
        self.progress_bar.setValue(100)
        self.footer_progress.setValue(100)
        
        # Actualizar stats
        self.completed_label.setText(f"{self.frames_completed} frames")
        self.status_label.setText(f"Frame {frame_num} completado en {time_seconds:.2f}s")
        
        # Simular datos enviados (estimación)
        frame_size_mb = 0.08  # ~80KB promedio
        self.total_data_sent += frame_size_mb
        self.data_sent_label.setText(f"{self.total_data_sent:.1f} MB")
        
        # Agregar el frame actual a la galería
        try:
            # Usar el pixmap que está en el preview (el último renderizado)
            pixmap = self.preview_label.pixmap()
            
            if pixmap and not pixmap.isNull():
                # Agregar a galería
                self.add_frame_to_gallery_from_pixmap(frame_num, pixmap)
        except Exception as e:
            print(f"Error agregando frame a galería: {e}")
            self.preview_label.setText(f"Frame {frame_num} completado!\n\n{time_seconds:.2f} segundos\n\nEsperando siguiente tarea...")
    
    def add_frame_to_gallery(self, frame_num):
        """Agregar frame completado a la galería."""
        try:
            # Usar el preview del label actual si existe
            pixmap = self.preview_label.pixmap()
            
            if pixmap and not pixmap.isNull():
                self.add_frame_to_gallery_from_pixmap(frame_num, pixmap)
                
        except Exception as e:
            print(f"Error agregando frame a galería: {e}")
    
    def add_frame_to_gallery_from_pixmap(self, frame_num, pixmap):
        """Agregar frame a galería desde un pixmap."""
        try:
            # Crear thumbnail
            thumbnail = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Crear label con frame
            frame_widget = QWidget()
            frame_layout = QVBoxLayout(frame_widget)
            frame_layout.setContentsMargins(2, 2, 2, 2)
            
            img_label = QLabel()
            img_label.setPixmap(thumbnail)
            img_label.setFrameStyle(QFrame.StyledPanel)
            frame_layout.addWidget(img_label)
            
            # Etiqueta con número de frame
            text_label = QLabel(f"Frame {frame_num}")
            text_label.setAlignment(Qt.AlignCenter)
            text_label.setFont(QFont("Segoe UI", 7))
            frame_layout.addWidget(text_label)
            
            # Agregar a grid (5 columnas)
            row = len(self.completed_frames) // 5
            col = len(self.completed_frames) % 5
            self.gallery_grid.addWidget(frame_widget, row, col)
            
            self.completed_frames.append((frame_num, pixmap))
            
        except Exception as e:
            print(f"Error agregando frame a galería desde pixmap: {e}")
    
    def closeEvent(self, event):
        """Manejar cierre de ventana"""
        if hasattr(self, 'worker_thread'):
            self.worker_thread.running = False
            self.worker_thread.quit()
            self.worker_thread.wait()
        event.accept()


def main():
    """Punto de entrada principal"""
    if len(sys.argv) < 2:
        print("Uso: python gui_worker.py <IP_MASTER>")
        sys.exit(1)
    
    scheduler_ip = sys.argv[1]
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = WorkerWindow(scheduler_ip)
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()