# worker_mandelbrot_zoom.py
# Worker que genera MÚLTIPLES FRAMES de Mandelbrot con zoom progresivo

import sys
import os
import time
from PIL import Image

def obtener_ip_local():
    """Obtiene la IP local de la máquina"""
    try:
        import socket
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip
    except:
        return "Desconocida"


def calcular_mandelbrot(x, y, max_iter):
    """
    Calcula el número de iteraciones para un punto (x,y) en el conjunto de Mandelbrot
    """
    c = complex(x, y)
    z = 0

    for n in range(max_iter):
        if abs(z) > 2:
            return n
        z = z * z + c

    return max_iter


def obtener_color(iteraciones, max_iter):
    """
    Convierte el número de iteraciones a un color RGB
    """
    if iteraciones == max_iter:
        return (0, 0, 0)
    else:
        ratio = iteraciones / max_iter
        r = int(255 * (ratio ** 0.5))
        g = int(255 * (ratio ** 0.3))
        b = int(255 * (1 - ratio ** 0.2))
        return (r, g, b)


def generar_frame_mandelbrot(frame_num, width, height, max_iter, x_min, x_max, y_min, y_max, output_file):
    """
    Genera un frame individual del Mandelbrot con los límites especificados
    """
    img = Image.new('RGB', (width, height))
    pixels = img.load()

    for row in range(height):
        for col in range(width):
            # Mapear píxel a coordenadas complejas
            x = x_min + (col / width) * (x_max - x_min)
            y = y_min + (row / height) * (y_max - y_min)

            # Calcular iteraciones de Mandelbrot
            iters = calcular_mandelbrot(x, y, max_iter)

            # Asignar color al píxel
            color = obtener_color(iters, max_iter)
            pixels[col, row] = color

    # Guardar imagen
    img.save(output_file)
    return output_file


def configurar_consola_windows():
    """Configura la consola de Windows para máxima visibilidad"""
    if os.name == 'nt':
        os.system('title WORKER MANDELBROT ZOOM - PROCESANDO')
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 3)
        except:
            pass
        os.system('color 0A')
        os.system('')


if _name_ == "_main_":
    if len(sys.argv) != 23:  # 1 script + 11 pares (--flag value) = 23
        print("Uso: python worker_mandelbrot_zoom.py --start-frame <N> --end-frame <N> --width <W> --height <H> --max-iter <N> --x-centro <F> --y-centro <F> --zoom-inicial <F> --zoom-final <F> --total-frames <N> --output-dir <path>")
        print(f"DEBUG: Recibí {len(sys.argv)} argumentos: {sys.argv}")
        sys.exit(1)

    # Parsear argumentos
    args = dict(zip(sys.argv[1::2], sys.argv[2::2]))

    START_FRAME = int(args.get('--start-frame', 0))
    END_FRAME = int(args.get('--end-frame', 10))
    WIDTH = int(args.get('--width', 800))
    HEIGHT = int(args.get('--height', 600))
    MAX_ITER = int(args.get('--max-iter', 100))
    X_CENTRO = float(args.get('--x-centro', -0.5))
    Y_CENTRO = float(args.get('--y-centro', 0.0))
    ZOOM_INICIAL = float(args.get('--zoom-inicial', 1.0))
    ZOOM_FINAL = float(args.get('--zoom-final', 100.0))
    TOTAL_FRAMES = int(args.get('--total-frames', 50))
    OUTPUT_DIR = args.get('--output-dir', 'C:\\Demo\\frames\\')

    # Crear directorio de salida si no existe
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Configurar consola
    configurar_consola_windows()
    os.system('cls' if os.name == 'nt' else 'clear')

    # Mostrar cabecera
    print("╔═══════════════════════════════════════════════════╗")
    print("║  🎬 WORKER MANDELBROT ZOOM - PROCESANDO          ║")
    print("╚═══════════════════════════════════════════════════╝")
    print()
    print(f"📍 Nodo: {obtener_ip_local()}")
    print(f"🎞  Frames asignados: {START_FRAME} → {END_FRAME} ({END_FRAME - START_FRAME} frames)")
    print(f"📐 Dimensiones: {WIDTH}x{HEIGHT} píxeles")
    print(f"🔢 Iteraciones máximas: {MAX_ITER}")
    print(f"🎯 Centro zoom: ({X_CENTRO}, {Y_CENTRO})")
    print(f"🔍 Zoom: {ZOOM_INICIAL}x → {ZOOM_FINAL}x")
    print(f"💾 Directorio salida: {OUTPUT_DIR}")
    print()
    print("═" * 51)
    print()

    inicio = time.time()
    frames_generados = []

    print("🎬 Generando frames con zoom progresivo...")
    print()

    # Generar cada frame asignado
    for frame_num in range(START_FRAME, END_FRAME):
        # Calcular nivel de zoom para este frame
        t = frame_num / (TOTAL_FRAMES - 1) if TOTAL_FRAMES > 1 else 0
        zoom_actual = ZOOM_INICIAL * (ZOOM_FINAL / ZOOM_INICIAL) ** t

        # Calcular límites de la ventana para este nivel de zoom
        ancho = 3.5 / zoom_actual  # Rango original: -2.5 a 1.0 = 3.5
        alto = 2.5 / zoom_actual   # Rango original: -1.25 a 1.25 = 2.5

        x_min = X_CENTRO - ancho / 2
        x_max = X_CENTRO + ancho / 2
        y_min = Y_CENTRO - alto / 2
        y_max = Y_CENTRO + alto / 2

        # Nombre del archivo de salida
        output_file = os.path.join(OUTPUT_DIR, f"frame_{frame_num:04d}.png")

        # Generar el frame
        generar_frame_mandelbrot(
            frame_num, WIDTH, HEIGHT, MAX_ITER,
            x_min, x_max, y_min, y_max,
            output_file
        )

        frames_generados.append(output_file)

        # Mostrar progreso
        frames_completados = frame_num - START_FRAME + 1
        total_asignados = END_FRAME - START_FRAME
        porcentaje = int(100 * frames_completados / total_asignados)
        barra_longitud = 30
        barra_llena = int(barra_longitud * porcentaje / 100)
        barra = '█' * barra_llena + '░' * (barra_longitud - barra_llena)

        tiempo_transcurrido = time.time() - inicio
        if frames_completados > 0:
            tiempo_estimado = tiempo_transcurrido * total_asignados / frames_completados
            tiempo_restante = tiempo_estimado - tiempo_transcurrido
            print(f"\r[{barra}] {porcentaje}% - Frame {frame_num}/{END_FRAME-1} - Zoom: {zoom_actual:.1f}x - ETA: {tiempo_restante:.1f}s", end='', flush=True)

    print()
    print()

    fin = time.time()
    tiempo_total = fin - inicio

    # Resumen final
    print("═" * 51)
    print("✅ TAREA COMPLETADA CON ÉXITO")
    print("═" * 51)
    print(f"⏱  Tiempo total: {tiempo_total:.2f} segundos")
    print(f"🎞  Frames generados: {len(frames_generados)}")
    print(f"📊 Píxeles totales: {WIDTH * HEIGHT * len(frames_generados):,}")
    print(f"🚀 Velocidad: {(WIDTH * HEIGHT * len(frames_generados)) / tiempo_total:,.0f} píxeles/segundo")
    print(f"💾 Directorio: {OUTPUT_DIR}")
    print("═" * 51)
    print()
    print("✅ Listo para que el MASTER descargue los frames")
    print()