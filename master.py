"""
Nodo Master para renderizado distribuido de fractales de Mandelbrot.

Este script coordina el renderizado distribuido, distribuye tareas a workers,
recopila frames completados y ensambla el video final.
"""

import time
import os
import sys
import imageio.v2 as imageio
from dask.distributed import Client, LocalCluster, as_completed
import dask

# Importar nueva infraestructura
from utils.config import config
from utils.logger import get_master_logger
from utils.network import get_local_ip
from utils.estimator import RenderEstimator
from utils.exceptions import RenderError

# Configurar Dask desde config.yaml
dask.config.set({
    "distributed.comm.timeouts.connect": config.get('cluster.timeouts.connect', '60s'),
    "distributed.comm.timeouts.tcp": config.get('cluster.timeouts.tcp', '60s'),
    "distributed.worker.profile.interval": config.get('cluster.worker.profile_interval', '2000ms'),
})

# Logger
logger = get_master_logger()

# Importar tarea de renderizado
try:
    from tareas import generar_frame_mandelbrot
except ImportError:
    logger.error("Falta el archivo 'tareas.py'")
    sys.exit(1)

# Importar sistema de persistencia
try:
    from utils.database import RenderDatabase
    from utils.progress_tracker import ProgressTracker, RecoveryManager
except ImportError as e:
    logger.error(f"Error importando módulos de persistencia: {e}")
    sys.exit(1)

# Estimador de tiempo
estimator = RenderEstimator()


def calcular_params_zoom(
    frame_num: int,
    total_frames: int,
    width: int,
    height: int,
    max_iter: int,
    x_centro: float,
    y_centro: float,
    zoom_inicial: float,
    zoom_final: float
) -> dict:
    """
    Calcula las coordenadas matemáticas para un frame específico.
    
    Args:
        frame_num: Número del frame (0-indexed)
        total_frames: Total de frames en la animación
        width: Ancho en píxeles
        height: Alto en píxeles
        max_iter: Iteraciones máximas
        x_centro, y_centro: Centro del zoom
        zoom_inicial: Zoom inicial
        zoom_final: Zoom final
    
    Returns:
        Diccionario con parámetros para renderizar el frame
    """
    t = frame_num / (total_frames - 1) if total_frames > 1 else 0
    # Interpolación exponencial para zoom suave
    zoom_actual = zoom_inicial * (zoom_final / zoom_inicial) ** t
    
    ancho = 3.5 / zoom_actual
    alto = 2.5 / zoom_actual
    
    return {
        'frame_num': frame_num,
        'width': width,
        'height': height,
        'max_iter': max_iter,
        'x_min': x_centro - ancho / 2,
        'x_max': x_centro + ancho / 2,
        'y_min': y_centro - alto / 2,
        'y_max': y_centro + alto / 2
    }


def main():
    """Función principal del master en modo CLI."""
    # Inicializar base de datos
    db = RenderDatabase()
    
    # Verificar si hay render pendiente de recuperar
    if ProgressTracker.has_pending_recovery():
        recovery_info = ProgressTracker.get_recovery_info()
        logger.warning("\n⚠️  RENDER INCOMPLETO DETECTADO")
        logger.warning(f"  Render ID: {recovery_info['render_id']}")
        logger.warning(f"  Completados: {recovery_info['completed_count']}/{recovery_info['completed_count'] + recovery_info['pending_count']}")
        logger.warning(f"  Iniciado: {recovery_info['started_at']}")
        
        respuesta = input("\n¿Deseas recuperar el render anterior? (s/n): ").lower()
        if respuesta == 's':
            # TODO: Implementar recuperación completa
            logger.info("Recuperación de renders pendiente de implementación en CLI")
            logger.info("Por ahora, usa el modo GUI para recuperación automática")
    
    # Cargar configuración
    output_dir = config.get('rendering.output_dir', './frames_renderizados')
    video_output = config.get('rendering.video_output', 'mandelbrot_zoom.mp4')
    fps = config.get('rendering.fps', 15)
    
    # Parámetros de renderizado desde config
    preset_name = config.get('rendering.default_preset', '720p_hd')
    
    # Cargar preset
    import json
    from pathlib import Path
    presets_file = Path(__file__).parent / 'config' / 'presets.json'
    
    with open(presets_file, 'r') as f:
        presets = json.load(f)
    
    preset = presets.get(preset_name, presets['720p_hd'])
    
    total_frames = preset['total_frames']
    width = preset['width']
    height = preset['height']
    max_iter = preset['max_iter']
    x_centro = preset['x_centro']
    y_centro = preset['y_centro']
    zoom_final = preset['zoom_final']
    zoom_inicial = 1.0
    
    os.makedirs(output_dir, exist_ok=True)
    ip = get_local_ip()
    
    logger.info("="*60)
    logger.info("MASTER DE RENDERIZADO - MANDELBROT ZOOM")
    logger.info("="*60)
    logger.info(f"Preset: {preset['name']} - {preset['description']}")
    logger.info(f"Resolución: {width}x{height}, Frames: {total_frames}, Iteraciones: {max_iter}")
    
    # Iniciar cluster
    scheduler_port = config.get('cluster.scheduler_port', 8786)
    dashboard_port = config.get('cluster.dashboard_port', 8787)
    
    logger.info("Iniciando cluster Dask...")
    cluster = LocalCluster(
        host=config.get('cluster.host', '0.0.0.0'),
        scheduler_port=scheduler_port,
        n_workers=config.get('cluster.n_workers', 0),
        dashboard_address=f':{dashboard_port}'
    )
    client = Client(cluster)
    
    logger.info(f"IP Master: {ip}")
    logger.info(f"Dashboard: http://{ip}:{dashboard_port}")
    logger.info("Esperando workers...")
    
    # Loop de espera interactivo
    while True:
        workers = client.scheduler_info()['workers']
        num_workers = len(workers)
        sys.stdout.write(f"\r   🔌 Workers conectados: {num_workers} (Presiona ENTER para iniciar render)")
        sys.stdout.flush()
        
        # Esperar input con timeout
        import select
        if sys.stdin in select.select([sys.stdin], [], [], 1)[0]:
            sys.stdin.readline()
            if num_workers > 0:
                break
            else:
                print("\n⚠️  ¡Necesitas al menos 1 worker conectado!")
    
    # Estimar tiempo
    use_optimized = config.get('rendering.use_optimized', True)
    estimated_time = estimator.estimate(
        width, height, max_iter, total_frames, num_workers, use_optimized
    )
    
    if estimated_time:
        logger.info(f"Tiempo estimado: {estimated_time/60:.1f} minutos con {num_workers} workers")
    
    logger.info(f"INICIANDO RENDERIZADO DE {total_frames} FRAMES")
    start_time = time.time()
    
    # Registrar render en base de datos
    render_config = {
        'preset': preset_name,
        'width': width,
        'height': height,
        'total_frames': total_frames,
        'max_iter': max_iter,
        'zoom_inicial': zoom_inicial,
        'zoom_final': zoom_final,
        'x_centro': x_centro,
        'y_centro': y_centro,
        'output_dir': output_dir
    }
    render_id = db.start_render('mandelbrot', render_config)
    logger.info(f"Render registrado con ID: {render_id}")
    
    # Inicializar tracker de progreso
    tracker = ProgressTracker(render_id)
    
    # Preparar tareas
    lista_tareas = [
        calcular_params_zoom(
            i, total_frames, width, height, max_iter,
            x_centro, y_centro, zoom_inicial, zoom_final
        )
        for i in range(total_frames)
    ]
    
    # Registrar frames en base de datos
    for i in range(total_frames):
        db.add_frame(render_id, i, status='pending')
    
    # Enviar al cluster
    futures = client.map(generar_frame_mandelbrot, lista_tareas)
    logger.info("Tareas enviadas. Recibiendo imágenes...")
    
    frames_guardados = 0
    frames_fallidos = 0
    completed_frames = set()
    failed_frames = set()
    pending_frames = set(range(total_frames))
    
    # Recibir resultados con timeout y retry
    for future in as_completed(futures):
        try:
            # NUEVO: Timeout de 5 minutos por frame
            num_frame, img_bytes = future.result(timeout=300)
            
            # Actualizar estado en DB
            db.update_frame(render_id, num_frame, 'rendering')
            
            # Descomprimir si es necesario
            if config.get('rendering.compress_frames', False):
                import zlib
                img_bytes = zlib.decompress(img_bytes)
            
            # Guardar frame
            nombre_archivo = f"frame_{num_frame:04d}.png"
            ruta_completa = os.path.join(output_dir, nombre_archivo)
            
            with open(ruta_completa, "wb") as f:
                f.write(img_bytes)
            
            file_size = len(img_bytes)
            frames_guardados += 1
            
            # Actualizar en base de datos
            db.update_frame(
                render_id, num_frame, 'completed',
                render_time=time.time() - start_time,
                file_path=ruta_completa,
                file_size=file_size
            )
            
            # Actualizar tracker de progreso
            completed_frames.add(num_frame)
            pending_frames.discard(num_frame)
            tracker.save_progress(completed_frames, failed_frames, pending_frames)
            
            # Barra de progreso
            porcentaje = int((frames_guardados / total_frames) * 100)
            barra = "█" * (porcentaje // 2) + "░" * ((100 - porcentaje) // 2)
            print(f"\r   [{barra}] {porcentaje}% - Guardado: {nombre_archivo}", end="")
            
        except TimeoutError:
            logger.error(f"TIMEOUT: Frame {num_frame} tardó más de 5 minutos")
            frames_fallidos += 1
            failed_frames.add(num_frame)
            pending_frames.discard(num_frame)
            db.update_frame(render_id, num_frame, 'failed', error_message='Timeout (300s)')
            tracker.save_progress(completed_frames, failed_frames, pending_frames)
            
        except Exception as e:
            logger.error(f"Error en frame {num_frame}: {e}")
            frames_fallidos += 1
            failed_frames.add(num_frame)
            pending_frames.discard(num_frame)
            db.update_frame(render_id, num_frame, 'failed', error_message=str(e))
            tracker.save_progress(completed_frames, failed_frames, pending_frames)
    
    tiempo_render = time.time() - start_time
    
    # Verificar completitud
    if frames_fallidos > 0:
        logger.warning(f"\n⚠️  RENDERIZADO INCOMPLETO: {frames_fallidos} frames fallidos")
        logger.warning(f"Completados: {frames_guardados}/{total_frames}")
        db.update_render_status(render_id, 'failed')
    else:
        logger.info(f"\n✅ RENDERIZADO COMPLETO en {tiempo_render:.2f}s ({tiempo_render/60:.1f} min)")
    
    # Registrar en estimador
    estimator.record(
        width, height, max_iter, total_frames,
        num_workers, tiempo_render, use_optimized
    )
    
    # Generar video solo si todos los frames están
    if frames_fallidos == 0:
        logger.info("Ensamblando video MP4...")
        try:
            writer = imageio.get_writer(video_output, fps=fps)
            
            for i in range(total_frames):
                ruta = os.path.join(output_dir, f"frame_{i:04d}.png")
                if os.path.exists(ruta):
                    img = imageio.imread(ruta)
                    writer.append_data(img)
                else:
                    logger.warning(f"Falta el frame {i}")
            
            writer.close()
            logger.info(f"VIDEO LISTO! -> {os.path.abspath(video_output)}")
            
            # Marcar como completado en DB
            db.complete_render(render_id, tiempo_render, os.path.abspath(video_output))
            tracker.clear()
            
        except Exception as e:
            logger.error(f"Error creando video: {e}")
            db.update_render_status(render_id, 'failed')
    else:
        logger.error("No se puede generar video con frames faltantes")
        logger.info("Frames fallidos guardados en la base de datos para reintentar")
    
    logger.info("PROCESO TERMINADO")
    if frames_fallidos == 0:
        logger.info(f"Video guardado en: {os.path.abspath(video_output)}")
    
    try:
        input("\n👋 Presiona ENTER para cerrar el Cluster y salir...")
    except KeyboardInterrupt:
        logger.info("Cerrando forzosamente (Ctrl+C)...")
    
    client.close()
    cluster.close()


if __name__ == "__main__":
    # Verificar si se solicita modo GUI o CLI
    if "--no-gui" in sys.argv:
        # Modo CLI original
        main()
    else:
        # Modo GUI
        try:
            from PyQt5.QtWidgets import QApplication
            from gui_master import MasterWindow
            
            app = QApplication(sys.argv)
            window = MasterWindow()
            window.show()
            sys.exit(app.exec_())
            
        except ImportError:
            print("ERROR: PyQt5 no esta instalado.")
            print("Instala con: pip install PyQt5")
            print("O ejecuta en modo CLI con: python master.py --no-gui")
            sys.exit(1)