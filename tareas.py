"""
Módulo de tareas para renderizado distribuido de fractales.

Este módulo contiene las funciones que se ejecutan en los workers
para generar frames del fractal de Mandelbrot.
"""

import io
import time
import zlib
import platform
from typing import Dict, Any, Tuple, Optional, Callable
from PIL import Image
import numpy as np

from fractals import MandelbrotRenderer, MandelbrotOptimizedRenderer
from utils.logger import get_render_logger
from utils.exceptions import RenderError, ValidationError
from utils.cache import FrameCache
from utils.config import config

# Intentar importar Dask Variable para progreso
try:
    from dask.distributed import Variable, get_worker
    DASK_AVAILABLE = True
except ImportError:
    DASK_AVAILABLE = False

# Logger para este módulo
logger = get_render_logger()

# Caché global (se inicializa si está habilitado)
_cache: Optional[FrameCache] = None

def _get_cache() -> Optional[FrameCache]:
    """Obtiene la instancia del caché (lazy initialization)."""
    global _cache
    if _cache is None and config.get('cache.enabled', False):
        cache_dir = config.get('cache.cache_dir', './cache')
        max_size = config.get('cache.max_size_mb', 1024)
        _cache = FrameCache(cache_dir, max_size)
    return _cache


def validate_params(params: Dict[str, Any]) -> None:
    """
    Valida los parámetros de renderizado.
    
    Args:
        params: Diccionario con parámetros
    
    Raises:
        ValidationError: Si los parámetros son inválidos
    """
    required_keys = ['frame_num', 'width', 'height', 'max_iter', 'x_min', 'x_max', 'y_min', 'y_max']
    
    for key in required_keys:
        if key not in params:
            raise ValidationError(f"Parámetro requerido faltante: {key}")
    
    if params['width'] <= 0 or params['height'] <= 0:
        raise ValidationError("Dimensiones deben ser positivas")
    
    if params['max_iter'] <= 0:
        raise ValidationError("max_iter debe ser positivo")
    
    if params['x_min'] >= params['x_max']:
        raise ValidationError("x_min debe ser menor que x_max")
    
    if params['y_min'] >= params['y_max']:
        raise ValidationError("y_min debe ser menor que y_max")


def _publish_worker_progress(frame_num: int, progress: int, status: str = 'rendering') -> None:
    """
    Publica el progreso del worker usando Dask Variables.
    
    Args:
        frame_num: Número del frame actual
        progress: Progreso en porcentaje (0-100)
        status: Estado ('started', 'rendering', 'completed')
    """
    if not DASK_AVAILABLE:
        return
    
    try:
        worker = get_worker()
        worker_name = worker.name
        
        # Crear variable única para este worker
        var = Variable(f'{worker_name}_progress', client=worker.client)
        
        # Publicar datos
        var.set({
            'frame_num': frame_num,
            'progress': progress,
            'status': status,
            'timestamp': time.time(),
            'worker_name': worker_name
        })
    except Exception as e:
        # No fallar si no se puede publicar
        logger.debug(f"No se pudo publicar progreso: {e}")


def generar_frame_fractal(
    params: Dict[str, Any],
    progress_callback: Optional[Callable[[int, int, Image.Image], None]] = None
) -> Tuple[int, bytes]:
    """
    Genera un frame completo de cualquier tipo de fractal.
    
    Soporta múltiples tipos de fractales (Mandelbrot, Julia, etc.)
    mediante selección dinámica del renderer basado en parámetros.
    
    Esta función puede usar la versión optimizada (NumPy/Numba) o la estándar
    según la configuración. También soporta caché y compresión.
    
    Args:
        params: Diccionario con parámetros de renderizado:
            - frame_num: Número del frame
            - width: Ancho en píxeles
            - height: Alto en píxeles
            - max_iter: Iteraciones máximas
            - x_min, x_max: Rango en eje X
            - y_min, y_max: Rango en eje Y
            - fractal_type: (opcional) 'mandelbrot' o 'julia' (default: 'mandelbrot')
            - fractal_params: (opcional) Dict con parámetros específicos del fractal
            - use_optimized: (opcional) Forzar versión optimizada
            - compress: (opcional) Comprimir resultado
        progress_callback: Callback opcional para reportar progreso
    
    Returns:
        Tupla (frame_num, img_bytes) donde img_bytes son los bytes PNG
    
    Raises:
        RenderError: Si hay error durante el renderizado
        ValidationError: Si los parámetros son inválidos
    """
    try:
        # Validar parámetros
        validate_params(params)
        
        frame_num = params['frame_num']
        width = params['width']
        height = params['height']
        max_iter = params['max_iter']
        x_min = params['x_min']
        x_max = params['x_max']
        y_min = params['y_min']
        y_max = params['y_max']
        
        # Publicar inicio
        _publish_worker_progress(frame_num, 0, 'started')
        
        # Verificar caché
        cache = _get_cache()
        if cache:
            cached_bytes = cache.get(params)
            if cached_bytes is not None:
                logger.info(f"Frame {frame_num} obtenido del caché")
                _publish_worker_progress(frame_num, 100, 'completed')
                return frame_num, cached_bytes
        
        # Determinar si usar versión optimizada
        use_optimized = params.get('use_optimized', config.get('rendering.use_optimized', True))
        
        # Determinar tipo de fractal y parámetros específicos
        fractal_type = params.get('fractal_type', 'mandelbrot')
        fractal_params = params.get('fractal_params', {})
        
        logger.info(f"Iniciando frame {frame_num} - {fractal_type} ({width}x{height}, {max_iter} iter) - "
                   f"Modo: {'Optimizado' if use_optimized else 'Estándar'}")
        
        # Publicar progreso 50% (renderizando)
        _publish_worker_progress(frame_num, 50, 'rendering')
        
        start_time = time.time()
        
        # Renderizar según modo y tipo de fractal
        if use_optimized:
            img_bytes = _render_optimized(
                fractal_type, fractal_params,
                frame_num, width, height, max_iter,
                x_min, x_max, y_min, y_max,
                progress_callback
            )
        else:
            img_bytes = _render_standard(
                fractal_type, fractal_params,
                frame_num, width, height, max_iter,
                x_min, x_max, y_min, y_max,
                progress_callback
            )
        
        elapsed = time.time() - start_time
        
        # Comprimir si está habilitado
        compress = params.get('compress', config.get('rendering.compress_frames', False))
        if compress:
            compression_level = config.get('rendering.compression_level', 6)
            img_bytes = zlib.compress(img_bytes, level=compression_level)
            logger.debug(f"Frame {frame_num} comprimido (nivel {compression_level})")
        
        # Guardar en caché
        if cache:
            cache.set(params, img_bytes)
        
        size_kb = len(img_bytes) / 1024
        logger.info(f"Frame {frame_num} completado en {elapsed:.2f}s ({size_kb:.1f} KB)")
        
        # Publicar completado
        _publish_worker_progress(frame_num, 100, 'completed')
        
        return frame_num, img_bytes
        
    except ValidationError:
        raise
    except Exception as e:
        logger.exception(f"Error renderizando frame {params.get('frame_num', '?')}")
        raise RenderError(f"Error en renderizado: {str(e)}")


def _render_standard(
    fractal_type: str,
    fractal_params: Dict[str, Any],
    frame_num: int,
    width: int,
    height: int,
    max_iter: int,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    progress_callback: Optional[Callable] = None
) -> bytes:
    """Renderiza usando versión estándar (Python puro)."""
    # Selección dinámica de renderer según tipo de fractal
    if fractal_type == 'mandelbrot':
        renderer = MandelbrotRenderer()
    elif fractal_type == 'julia':
        from fractals import JuliaRenderer
        c_real = fractal_params.get('c_real', -0.7)
        c_imag = fractal_params.get('c_imag', 0.27015)
        renderer = JuliaRenderer(c_real, c_imag)
    else:
        raise ValueError(f"Tipo de fractal no soportado: {fractal_type}")
    
    # Crear imagen en blanco
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    # Renderizar píxel por píxel
    for row in range(height):
        for col in range(width):
            # Mapear píxel a coordenada compleja
            x = x_min + (col / width) * (x_max - x_min)
            y = y_min + (row / height) * (y_max - y_min)
            
            iters = renderer.calculate(complex(x, y), max_iter)
            pixels[col, row] = renderer.get_color(iters, max_iter)
        
        # Reportar progreso
        if progress_callback and row % 50 == 0 and row > 0:
            try:
                progress_callback(row, height, img.copy())
            except Exception as e:
                logger.warning(f"Error en progress callback: {e}")
    
    # Convertir a bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()


def _render_optimized(
    fractal_type: str,
    fractal_params: Dict[str, Any],
    frame_num: int,
    width: int,
    height: int,
    max_iter: int,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    progress_callback: Optional[Callable] = None
) -> bytes:
    """Renderiza usando versión optimizada (NumPy/Numba) con visualización progresiva."""
    import json
    import os
    
    # Cargar configuración de visualización
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'visualization.json')
        with open(config_path, 'r') as f:
            viz_config = json.load(f)
        lines_per_update = viz_config['progressive_rendering']['lines_per_update']
        adaptive_delay = viz_config['progressive_rendering']['adaptive_delay']
        max_delay_ms = viz_config['progressive_rendering']['max_delay_per_line_ms']
        adaptive_threshold = viz_config['progressive_rendering']['adaptive_threshold_lines_per_sec']
    except:
        lines_per_update = 10
        adaptive_delay = True
        max_delay_ms = 50
        adaptive_threshold = 100
    
    # Selección dinámica de renderer optimizado según tipo de fractal
    if fractal_type == 'mandelbrot':
        renderer = MandelbrotOptimizedRenderer()
    elif fractal_type == 'julia':
        from fractals import JuliaOptimizedRenderer
        c_real = fractal_params.get('c_real', -0.7)
        c_imag = fractal_params.get('c_imag', 0.27015)
        renderer = JuliaOptimizedRenderer(c_real, c_imag)
    else:
        raise ValueError(f"Tipo de fractal no soportado: {fractal_type}")
    
    # Publicar inicio con metadata
    _publish_worker_progress(frame_num, 0, 'started')
    
    # Calcular iteraciones (fase 1: cálculo matemático)
    calc_start = time.time()
    iterations = renderer.calculate_array(width, height, x_min, x_max, y_min, y_max, max_iter)
    calc_time = time.time() - calc_start
    
    # Publicar progreso después del cálculo (30%)
    _publish_worker_progress(frame_num, 30, 'rendering')
    
    # Convertir a RGB con callback progresivo (fase 2: colorización)
    rgb_start = time.time()
    lines_rendered = 0
    last_update_time = time.time()
    
    def progressive_callback(current_row, total_rows, partial_rgb):
        """Callback que publica previews progresivos."""
        nonlocal lines_rendered, last_update_time
        
        lines_rendered = current_row
        
        # Actualizar cada N líneas
        if current_row % lines_per_update == 0 and current_row > 0:
            try:
                # Calcular progreso (30% a 90% durante colorización)
                progress = 30 + int((current_row / total_rows) * 60)
                
                # Calcular velocidad de renderizado
                elapsed = time.time() - rgb_start
                lines_per_sec = current_row / elapsed if elapsed > 0 else 0
                
                # Delay adaptivo: solo si es muy rápido
                if adaptive_delay and lines_per_sec > adaptive_threshold:
                    delay_sec = (max_delay_ms / 1000.0) * lines_per_update
                    time.sleep(delay_sec)
                
                # Publicar progreso con metadata
                if DASK_AVAILABLE:
                    try:
                        worker = get_worker()
                        worker_name = worker.name
                        
                        # Actualizar progreso (mantener Dask Variable para el master)
                        var = Variable(f'{worker_name}_progress', client=worker.client)
                        var.set({
                            'frame_num': frame_num,
                            'progress': progress,
                            'status': 'rendering',
                            'lines_completed': current_row,
                            'total_lines': total_rows,
                            'lines_per_sec': round(lines_per_sec, 1),
                            'timestamp': time.time()
                        })
                        
                        # Guardar preview en archivo temporal para el worker GUI
                        import os
                        import json
                        os.makedirs('./temp_previews', exist_ok=True)
                        
                        # Guardar imagen
                        partial_img = Image.fromarray(partial_rgb, 'RGB')
                        preview_path = f'./temp_previews/{worker_name}_preview.png'
                        partial_img.save(preview_path, format='PNG', optimize=False)
                        
                        # Guardar metadata
                        metadata_path = f'./temp_previews/{worker_name}_metadata.json'
                        with open(metadata_path, 'w') as f:
                            json.dump({
                                'frame_num': frame_num,
                                'lines_completed': current_row,
                                'total_lines': total_rows,
                                'lines_per_sec': round(lines_per_sec, 1),
                                'progress': progress,
                                'is_partial': True,
                                'timestamp': time.time()
                            }, f)
                        
                    except:
                        pass
                        
            except Exception as e:
                logger.debug(f"Error en progressive callback: {e}")
    
    # Renderizar con callback progresivo
    rgb_array = renderer.render_to_rgb_progressive(
        iterations, 
        max_iter, 
        progressive_callback,
        lines_per_update
    )
    
    # Publicar progreso al 95% (casi completo)
    _publish_worker_progress(frame_num, 95, 'rendering')
    
    # Convertir a imagen PIL final
    img = Image.fromarray(rgb_array, 'RGB')
    
    # Convertir a bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    
    # Publicar preview final completo
    if DASK_AVAILABLE:
        try:
            worker = get_worker()
            worker_name = worker.name
            
            preview_var = Variable(f'{worker_name}_preview', client=worker.client)
            preview_var.set({
                'frame_num': frame_num,
                'preview_bytes': img_bytes,
                'lines_completed': height,
                'total_lines': height,
                'is_partial': False,
                'timestamp': time.time()
            })
        except:
            pass
    
    return img_bytes


# Mantener alias para compatibilidad backward
generar_frame_mandelbrot = generar_frame_fractal


# Mantener funciones legacy para compatibilidad
def calcular_mandelbrot(c: complex, max_iter: int) -> int:
    """
    Calcula iteraciones para un número complejo (función legacy).
    
    DEPRECATED: Usar MandelbrotRenderer.calculate() en su lugar.
    """
    renderer = MandelbrotRenderer()
    return renderer.calculate(c, max_iter)


def obtener_color(iteraciones: int, max_iter: int) -> Tuple[int, int, int]:
    """
    Genera color basado en iteraciones (función legacy).
    
    DEPRECATED: Usar MandelbrotRenderer.get_color() en su lugar.
    """
    renderer = MandelbrotRenderer()
    return renderer.get_color(iteraciones, max_iter)