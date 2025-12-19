import io
from PIL import Image

def calcular_mandelbrot(c, max_iter):
    """Calcula iteraciones para un número complejo c."""
    z = 0
    for n in range(max_iter):
        if abs(z) > 2:
            return n
        z = z * z + c
    return max_iter

def obtener_color(iteraciones, max_iter):
    """Genera un color psicodélico basado en las iteraciones."""
    if iteraciones == max_iter:
        return (0, 0, 0)
    else:
        # Algoritmo de color del código original
        ratio = iteraciones / max_iter
        r = int(255 * (ratio ** 0.5))
        g = int(255 * (ratio ** 0.3))
        b = int(255 * (1 - ratio ** 0.2))
        return (r, g, b)

def generar_frame_mandelbrot(params, progress_callback=None):
    """
    Genera un frame completo en memoria.
    Recibe un diccionario 'params' para facilitar el envío con Dask.
    Opcionalmente acepta progress_callback(row, total_rows, img_copy) para GUI.
    Retorna: (número_frame, bytes_de_la_imagen)
    """
    # Desempaquetamos parámetros
    frame_num = params['frame_num']
    width = params['width']
    height = params['height']
    max_iter = params['max_iter']
    x_min = params['x_min']
    x_max = params['x_max']
    y_min = params['y_min']
    y_max = params['y_max']

    # Creamos imagen en blanco en memoria
    img = Image.new('RGB', (width, height))
    pixels = img.load()

    # Log para que veas trabajar al worker
    print(f"[FRAME {frame_num}] Renderizando Mandelbrot...", flush=True)

    for row in range(height):
        for col in range(width):
            # Mapeo de píxel a coordenada compleja
            x = x_min + (col / width) * (x_max - x_min)
            y = y_min + (row / height) * (y_max - y_min)
            
            iters = calcular_mandelbrot(complex(x, y), max_iter)
            pixels[col, row] = obtener_color(iters, max_iter)
        
        # Reportar progreso cada 50 filas para GUI
        if progress_callback and row % 50 == 0 and row > 0:
            try:
                progress_callback(row, height, img.copy())
            except Exception as e:
                # No fallar si el callback tiene problemas
                print(f"[WARNING] Progress callback error: {e}", flush=True)

    # Convertimos la imagen a BYTES para enviarla por la red
    # (Así no guardamos archivos en el disco del worker)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    print(f"[FRAME {frame_num}] Listo. Enviando {len(img_bytes)/1024:.1f} KB al Master.", flush=True)
    
    return frame_num, img_bytes