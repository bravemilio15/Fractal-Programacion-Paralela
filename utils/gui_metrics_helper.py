"""
Extensión de GUI para métricas en tiempo real de GPU/CPU.

Funciones helper para añadir al gui_master.py
"""

from PyQt5.QtWidgets import (QGroupBox, QVBoxLayout, QLabel, 
                             QPushButton, QProgressBar, QHBoxLayout)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont


def add_metrics_panel_to_dashboard(parent_window):
    """
    Añadir panel de métricas en tiempo real al dashboard.
    
    Args:
        parent_window: Instancia de MasterWindow
        
    Returns:
        QGroupBox con el panel de métricas
    """
    metrics_group = QGroupBox("📊 Métricas en Tiempo Real")
    metrics_layout = QVBoxLayout()
    
    # Backend status label (grande, colorido)
    parent_window.backend_status_label = QLabel("ESPERANDO...")
    parent_window.backend_status_label.setStyleSheet("""
        QLabel {
            background-color: #34495e;
            color: white;
            font-size: 18px;
            font-weight: bold;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }
    """)
    parent_window.backend_status_label.setFont(QFont("Arial", 14, QFont.Bold))
    metrics_layout.addWidget(parent_window.backend_status_label)
    
    # GPU Memory section
    gpu_mem_layout = QHBoxLayout()
    gpu_mem_layout.addWidget(QLabel("GPU Memory:"))
    parent_window.gpu_mem_label = QLabel("-- MB / -- GB")
    gpu_mem_layout.addWidget(parent_window.gpu_mem_label)
    metrics_layout.addLayout(gpu_mem_layout)
    
    parent_window.gpu_mem_bar = QProgressBar()
    parent_window.gpu_mem_bar.setRange(0, 100)
    parent_window.gpu_mem_bar.setValue(0)
    parent_window.gpu_mem_bar.setStyleSheet("""
        QProgressBar {
            border: 2px solid #555;
            border-radius: 5px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #00ff00;
        }
    """)
    metrics_layout.addWidget(parent_window.gpu_mem_bar)
    
    # CPU Usage
    cpu_layout = QHBoxLayout()
    cpu_layout.addWidget(QLabel("CPU Usage:"))
    parent_window.cpu_usage_label = QLabel("-- %")
    cpu_layout.addWidget(parent_window.cpu_usage_label)
    metrics_layout.addLayout(cpu_layout)
    
    parent_window.cpu_usage_bar = QProgressBar()
    parent_window.cpu_usage_bar.setRange(0, 100)
    parent_window.cpu_usage_bar.setValue(0)
    parent_window.cpu_usage_bar.setStyleSheet("""
        QProgressBar {
            border: 2px solid #555;
            border-radius: 5px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #ffaa00;
        }
    """)
    metrics_layout.addWidget(parent_window.cpu_usage_bar)
    
    # FPS Counter
    fps_layout = QHBoxLayout()
    fps_layout.addWidget(QLabel("Frames/Segundo:"))
    parent_window.fps_label = QLabel("0.0 fps")
    parent_window.fps_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2ecc71;")
    fps_layout.addWidget(parent_window.fps_label)
    metrics_layout.addLayout(fps_layout)
    
    # Total frames completed
    frames_layout = QHBoxLayout()
    frames_layout.addWidget(QLabel("Frames:"))
    parent_window.frames_count_label = QLabel("0 / 0")
    frames_layout.addWidget(parent_window.frames_count_label)
    metrics_layout.addLayout(frames_layout)
    
    metrics_group.setLayout(metrics_layout)
    return metrics_group


def update_metrics_display(parent_window):
    """
    Actualizar el display de métricas en tiempo real.
    
    Args:
        parent_window: Instancia de MasterWindow
    """
    if not hasattr(parent_window, 'backend_status_label'):
        return
    
    # Determinar backend activo
    is_cuda = parent_window.gpu_radio.isChecked()
    is_rendering = parent_window.render_thread is not None and parent_window.render_thread.isRunning()
    
    if not is_rendering:
        parent_window.backend_status_label.setText("⏸ ESPERANDO")
        parent_window.backend_status_label.setStyleSheet("""
            QLabel {
                background-color: #34495e;
                color: white;
                font-size: 18px;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
        """)
        return
    
    # Actualizar según backend
    if is_cuda:
        parent_window.backend_status_label.setText("🚀 CUDA GPU RENDERING")
        parent_window.backend_status_label.setStyleSheet("""
            QLabel {
                background-color: #00ff00;
                color: black;
                font-size: 18px;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
        """)
        
        # Obtener stats GPU
        stats = parent_window.gpu_monitor.get_combined_stats()
        
        if stats.get('cuda_available'):
            mem_used = stats['memory_used_mb']
            mem_total_gb = stats['memory_total_gb']
            
            parent_window.gpu_mem_label.setText(
                f"{mem_used:.1f} MB / {mem_total_gb:.2f} GB"
            )
            parent_window.gpu_mem_bar.setValue(int(stats['memory_percent']))
            
            # CPU debería estar bajo cuando GPU trabaja
            cpu = stats['cpu_percent']
            parent_window.cpu_usage_label.setText(f"{cpu:.0f}% (bajo = GPU activa)")
            parent_window.cpu_usage_bar.setValue(int(cpu))
        else:
            parent_window.gpu_mem_label.setText("CUDA no disponible")
            parent_window.gpu_mem_bar.setValue(0)
    else:
        parent_window.backend_status_label.setText("⚡ CPU (NUMBA) RENDERING")
        parent_window.backend_status_label.setStyleSheet("""
            QLabel {
                background-color: #ffaa00;
                color: black;
                font-size: 18px;
                font-weight: bold;
                padding: 15px;
                border-radius: 5px;
            }
        """)
        
        # CPU alto cuando usa Numba
        stats = parent_window.gpu_monitor.get_combined_stats()
        cpu = stats['cpu_percent']
        parent_window.cpu_usage_label.setText(f"{cpu:.0f}% (alto = CPU activa)")
        parent_window.cpu_usage_bar.setValue(int(cpu))
        
        parent_window.gpu_mem_label.setText("No usa GPU")
        parent_window.gpu_mem_bar.setValue(0)
    
    # Actualizar FPS
    perf_stats = parent_window.perf_tracker.get_stats()
    fps = perf_stats.get('fps', 0)
    parent_window.fps_label.setText(f"{fps:.2f} fps")
    
    # Frames completados
    frames_done = perf_stats.get('frames_completed', 0)
    # ProgressTracker usa config_data['total_frames'], no total_frames directo
    total_frames = 0
    if parent_window.tracker:
        try:
            total_frames = parent_window.tracker.config_data.get('total_frames', 0)
        except:
            total_frames = 0
    parent_window.frames_count_label.setText(f"{frames_done} / {total_frames}")


def start_metrics_timer(parent_window):
    """
    Iniciar timer para actualizar métricas cada 500ms.
    
    Args:
        parent_window: Instancia de MasterWindow
    """
    if parent_window.metrics_timer is None:
        parent_window.metrics_timer = QTimer()
        parent_window.metrics_timer.timeout.connect(
            lambda: update_metrics_display(parent_window)
        )
    
    parent_window.metrics_timer.start(500)  # 500ms


def stop_metrics_timer(parent_window):
    """
    Detener timer de métricas.
    
    Args:
        parent_window: Instancia de MasterWindow
    """
    if parent_window.metrics_timer:
        parent_window.metrics_timer.stop()


def detect_gpu_capability(parent_window):
    """
    Detectar capacidad GPU y actualizar label de status.
    
    Args:
        parent_window: Instancia de MasterWindow
    """
    stats = parent_window.gpu_monitor.get_gpu_stats()
    
    if stats.get('cuda_available'):
        from fractals import get_gpu_info
        gpu_info = get_gpu_info()
        
        if gpu_info:
            msg = f"✓ GPU: {gpu_info['name']}\n"
            msg += f"Memoria: {gpu_info['memory_total']:.1f} GB\n"
            msg += f"Compute Capability: {gpu_info['compute_capability']}"
            
            parent_window.gpu_status_label.setText(msg)
            parent_window.gpu_status_label.setStyleSheet("color: #00ff00; font-size: 11px;")
        else:
            parent_window.gpu_status_label.setText("✓ CUDA disponible")
            parent_window.gpu_status_label.setStyleSheet("color: #00ff00; font-size: 11px;")
    else:
        parent_window.gpu_status_label.setText("✗ CUDA no disponible (CPU mode)")
        parent_window.gpu_status_label.setStyleSheet("color: #ff6666; font-size: 11px;")


def update_gpu_status_label(parent_window):
    """
    Actualizar label de status GPU inicial.
    
    Args:
        parent_window: Instancia de MasterWindow
    """
    detect_gpu_capability(parent_window)
