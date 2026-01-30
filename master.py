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
    from tareas import generar_frame_fractal, generar_frame_mandelbrot
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
    Calcula las coordenadas matemáticas para un frame específico de Mandelbrot.
    
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
        'y_max': y_centro + alto / 2,
        'fractal_type': 'mandelbrot'
    }


def calcular_params_julia(
    frame_num: int,
    total_frames: int,
    width: int,
    height: int,
    max_iter: int,
    c_real: float,
    c_imag: float,
    x_centro: float = 0.0,
    y_centro: float = 0.0,
    zoom_inicial: float = 1.0,
    zoom_final: float = 1.0
) -> dict:
    """
    Calcula parámetros para el conjunto de Julia.
    
    A diferencia de Mandelbrot, Julia normalmente no necesita zoom profundo
    ya que la estructura es globalmente interesante. Se recomienda zoom moderado
    o paneos en el plano complejo.
    
    Args:
        frame_num: Número del frame
        total_frames: Total de frames
        width, height: Dimensiones en píxeles
        max_iter: Iteraciones máximas
        c_real, c_imag: Constante c del conjunto de Julia
        x_centro, y_centro: Centro de la región de interés
        zoom_inicial, zoom_final: Nivel de zoom (1.0 = completo)
    
    Returns:
        Diccionario con parámetros para renderizar el frame
    """
    t = frame_num / (total_frames - 1) if total_frames > 1 else 0
    
    # Zoom suave (opcional, Julia es interesante sin mucho zoom)
    zoom_actual = zoom_inicial * (zoom_final / zoom_inicial) ** t
    
    # Región típica: [-2, 2] x [-2, 2]
    ancho = 4.0 / zoom_actual
    alto = 4.0 / zoom_actual
    
    return {
        'frame_num': frame_num,
        'width': width,
        'height': height,
        'max_iter': max_iter,
        'x_min': x_centro - ancho / 2,
        'x_max': x_centro + ancho / 2,
        'y_min': y_centro - alto / 2,
        'y_max': y_centro + alto / 2,
        'fractal_type': 'julia',
        'fractal_params': {
            'c_real': c_real,
            'c_imag': c_imag
        }
    }


def main():
    """Función principal del master en modo CLI."""
    # Inicializar base de datos
    db = RenderDatabase()
    
    # Registrar tipos de fractales en la base de datos (si no existen)
    db.add_fractal_type(
        name='mandelbrot',
        description='Conjunto de Mandelbrot - z(n+1) = z(n)^2 + c, z0=0',
        renderer_class='fractals.mandelbrot.MandelbrotRenderer'
    )
    db.add_fractal_type(
        name='julia',
        description='Conjunto de Julia - z(n+1) = z(n)^2 + c, c=constante',
        renderer_class='fractals.julia.JuliaRenderer'
    )
    
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
    base_output_dir = config.get('rendering.output_dir', './frames_renderizados')
    video_output = config.get('rendering.video_output', 'mandelbrot_zoom.mp4')
    fps = config.get('rendering.fps', 15)
    
    # Determinar tipo de fractal desde configuración
    fractal_type = config.get('rendering.fractal_type', 'mandelbrot')
    
    # Crear directorio único con timestamp para este render
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fractal_type == 'julia':
        c_real = config.get('fractals.julia.c_real', -0.7)
        c_imag = config.get('fractals.julia.c_imag', 0.27015)
        render_name = f"julia_c{c_real:.3f}{c_imag:+.3f}i_{timestamp}"
    else:
        render_name = f"{fractal_type}_{timestamp}"
    
    output_dir = os.path.join(base_output_dir, render_name)
    video_output = os.path.join(output_dir, f"{render_name}.mp4")
    
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
    
    # Cargar parámetros específicos del fractal
    if fractal_type == 'julia':
        c_real = config.get('fractals.julia.c_real', -0.7)
        c_imag = config.get('fractals.julia.c_imag', 0.27015)
        logger.info(f"Conjunto de Julia seleccionado (c = {c_real}{c_imag:+.4f}i)")
    
    os.makedirs(output_dir, exist_ok=True)
    ip = get_local_ip()
    
    logger.info("="*60)
    logger.info(f"MASTER DE RENDERIZADO - {fractal_type.upper()} ZOOM")
    logger.info("="*60)
    logger.info(f"Preset: {preset['name']} - {preset['description']}")
    logger.info(f"Resolución: {width}x{height}, Frames: {total_frames}, Iteraciones: {max_iter}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Video: {video_output}")
    
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
    
    logger.info(f"INICIANDO RENDERIZADO DE {total_frames} FRAMES - {fractal_type.upper()}")
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
    
    # Agregar parámetros específicos de Julia si aplica
    if fractal_type == 'julia':
        render_config['c_real'] = c_real
        render_config['c_imag'] = c_imag
    
    render_id = db.start_render(fractal_type, render_config)
    logger.info(f"Render registrado con ID: {render_id}")
    
    # Inicializar tracker de progreso
    tracker = ProgressTracker(render_id)
    
    # Preparar tareas según tipo de fractal
    if fractal_type == 'mandelbrot':
        lista_tareas = [
            calcular_params_zoom(
                i, total_frames, width, height, max_iter,
                x_centro, y_centro, zoom_inicial, zoom_final
            )
            for i in range(total_frames)
        ]
    elif fractal_type == 'julia':
        lista_tareas = [
            calcular_params_julia(
                i, total_frames, width, height, max_iter,
                c_real, c_imag, x_centro, y_centro, zoom_inicial, zoom_final
            )
            for i in range(total_frames)
        ]
    else:
        logger.error(f"Tipo de fractal no soportado: {fractal_type}")
        sys.exit(1)
    
    # Registrar frames en base de datos
    for i in range(total_frames):
        db.add_frame(render_id, i, status='pending')
    
    # Enviar al cluster (usar función genérica)
    futures = client.map(generar_frame_fractal, lista_tareas)
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
            
            frames_agregados = 0
            frames_corruptos = 0
            
            for i in range(total_frames):
                ruta = os.path.join(output_dir, f"frame_{i:04d}.png")
                if os.path.exists(ruta):
                    try:
                        # Intentar cargar frame con PIL primero para validar
                        from PIL import Image
                        img_test = Image.open(ruta)
                        img_test.verify()  # Verificar integridad
                        
                        # Si pasó verificación, agregarlo al video
                        img_test.close()
                        frame = imageio.imread(ruta)
                        writer.append_data(frame)
                        frames_agregados += 1
                        
                        if (i + 1) % 10 == 0:
                            logger.info(f"Video: {frames_agregados}/{total_frames} frames agregados")
                    
                    except Exception as e:
                        frames_corruptos += 1
                        logger.warning(f"⚠️  Frame {i} corrupto, omitiendo: {e}")
                        # Continuar con el siguiente frame
                        continue
                else:
                    logger.warning(f"Frame {i} no encontrado: {ruta}")
            
            writer.close()
            
            if frames_corruptos > 0:
                logger.warning(f"⚠️  Video generado con {frames_corruptos} frames corruptos omitidos")
                logger.info(f"✅ Video guardado: {video_output} ({frames_agregados}/{total_frames} frames)")
            else:
                logger.info(f"✅ Video guardado exitosamente: {video_output}")
            
            # Actualizar DB solo si video se generó
            db.complete_render(render_id, tiempo_render)
            tracker.clear()
            
        except Exception as e:
            logger.error(f"Error ensamblando video: {e}")
            logger.info("Frames guardados en: " + output_dir)
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