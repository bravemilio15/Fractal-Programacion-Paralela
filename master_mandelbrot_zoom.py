# master_mandelbrot_zoom.py
# MAESTRO: Coordina 2 workers para generar animación con zoom del Mandelbrot
# IMPORTANTE: Este master NO calcula nada, solo coordina y ensambla

from fabric import Connection
import time
import os
import threading

# --- CONFIGURACIÓN DE NODOS ---
HOSTS = [
    {
        "ip": "192.168.1.3",
        "user": "Baller 293",
        "pass": "Baller.293",
        "nombre": "Worker1"
    },
    {
        "ip": "192.168.1.25",
        "user": "ASUS",
        "pass": "12345678",
        "nombre": "Worker2-ASUS"
    }
]

# --- CONFIGURACIÓN DE LA ANIMACIÓN ---
TOTAL_FRAMES = 50        # Total de fotogramas para la animación
WIDTH = 800              # Ancho de cada frame
HEIGHT = 600             # Alto de cada frame
MAX_ITER = 100           # Iteraciones máximas

# Parámetros del zoom
X_CENTRO = -0.7          # Coordenada X del punto de zoom (zona interesante)
Y_CENTRO = 0.0           # Coordenada Y del punto de zoom
ZOOM_INICIAL = 1.0       # Nivel de zoom inicial (vista completa)
ZOOM_FINAL = 100.0       # Nivel de zoom final (muy cerca)

# --- RUTAS EN WINDOWS (WORKERS) ---
RUTA_WORKER_REMOTO = "C:\\Demo\\worker_mandelbrot_zoom.py"
RUTA_FRAMES_REMOTO = "C:\\Demo\\frames\\"

# --- CARPETA LOCAL PARA RESULTADOS ---
CARPETA_FRAMES_LOCAL = "./frames_mandelbrot/"
CARPETA_RESULTADOS_LOCAL = "./resultados_mandelbrot/"
os.makedirs(CARPETA_FRAMES_LOCAL, exist_ok=True)
os.makedirs(CARPETA_RESULTADOS_LOCAL, exist_ok=True)

print("=" * 70)
print("CLUSTER MANDELBROT ZOOM - GENERADOR DE ANIMACIÓN DISTRIBUIDA")
print("=" * 70)
print(f"Total de frames: {TOTAL_FRAMES}")
print(f"Resolución: {WIDTH}x{HEIGHT} píxeles")
print(f"Iteraciones: {MAX_ITER}")
print(f"Zoom: {ZOOM_INICIAL}x → {ZOOM_FINAL}x")
print(f"Centro: ({X_CENTRO}, {Y_CENTRO})")
print(f"Número de workers: {len(HOSTS)}")
print()
print("IMPORTANTE: El MASTER no realizará ningún cálculo.")
print("            Solo coordinará workers y ensamblará el video.")
print()

# --- VALIDACIÓN DE WORKERS ---
if not HOSTS:
    print("✗ ERROR: No hay workers definidos en la lista HOSTS.")
    print("         El master no puede realizar cálculos. Agregue al menos un worker.")
    exit(1)

# --- DIVIDIR TRABAJO ENTRE WORKERS ---
frames_por_worker = TOTAL_FRAMES // len(HOSTS)
frames_extra = TOTAL_FRAMES % len(HOSTS)

print("DISTRIBUCIÓN DE TRABAJO:")
frame_start = 0
asignaciones = []

for i, host in enumerate(HOSTS):
    frames_asignados = frames_por_worker + (1 if i < frames_extra else 0)
    frame_end = frame_start + frames_asignados

    asignaciones.append({
        "host": host,
        "start": frame_start,
        "end": frame_end,
        "total": frames_asignados
    })

    print(f"  • {host['nombre']} ({host['ip']}): Frames {frame_start}-{frame_end-1} ({frames_asignados} frames)")
    frame_start = frame_end

print()

# --- FUNCIÓN PARA EJECUTAR EN CADA WORKER (EN PARALELO) ---
def ejecutar_worker(asignacion, worker_id):
    """Ejecuta el trabajo en un worker específico"""
    host = asignacion['host']
    start_frame = asignacion['start']
    end_frame = asignacion['end']

    comando = (
        f"python {RUTA_WORKER_REMOTO} "
        f"--start-frame {start_frame} "
        f"--end-frame {end_frame} "
        f"--width {WIDTH} "
        f"--height {HEIGHT} "
        f"--max-iter {MAX_ITER} "
        f"--x-centro {X_CENTRO} "
        f"--y-centro {Y_CENTRO} "
        f"--zoom-inicial {ZOOM_INICIAL} "
        f"--zoom-final {ZOOM_FINAL} "
        f"--total-frames {TOTAL_FRAMES} "
        f"--output-dir {RUTA_FRAMES_REMOTO}"
    )

    print(f"\n[{host['nombre']}] Conectando a {host['ip']}...")
    print(f"[{host['nombre']}] Frames asignados: {start_frame}-{end_frame-1}")
    print(f"[{host['nombre']}] Comando: {comando[:80]}...")
    print()

    try:
        with Connection(
            host=host['ip'],
            user=host['user'],
            connect_kwargs={
                "password": host['pass'],
                "look_for_keys": False,
                "allow_agent": False
            }
        ) as c:
            # Ejecutar worker en el nodo remoto
            print(f"[{host['nombre']}] ⏳ Iniciando generación de frames...")
            resultado = c.run(comando, hide=False, pty=True)

            print()
            print(f"[{host['nombre']}] ✓ Frames generados exitosamente")
            print()

            # Descargar los frames generados
            print(f"[{host['nombre']}] 📥 Descargando {end_frame - start_frame} frames...")

            import base64
            for frame_num in range(start_frame, end_frame):
                archivo_remoto = f"{RUTA_FRAMES_REMOTO}frame_{frame_num:04d}.png"
                archivo_local = os.path.join(CARPETA_FRAMES_LOCAL, f"frame_{frame_num:04d}.png")

                try:
                    # Descargar usando base64 (método que funciona)
                    result = c.run(
                        f'powershell -Command "[Convert]::ToBase64String([IO.File]::ReadAllBytes(\'{archivo_remoto}\'))"',
                        hide=True
                    )
                    file_data = base64.b64decode(result.stdout.strip())
                    with open(archivo_local, 'wb') as f:
                        f.write(file_data)

                    if (frame_num - start_frame + 1) % 5 == 0:
                        print(f"[{host['nombre']}] Descargados: {frame_num - start_frame + 1}/{end_frame - start_frame} frames", end='\r', flush=True)
                except Exception as e:
                    print(f"\n[{host['nombre']}] ✗ Error descargando frame {frame_num}: {e}")

            print()
            print(f"[{host['nombre']}] ✓ Todos los frames descargados")

    except Exception as e:
        print(f"\n[{host['nombre']}] ✗ ERROR: {e}")
        print()

# --- EJECUTAR WORKERS EN PARALELO ---
print("=" * 70)
print("FASE 1: Enviando tareas a workers (EN PARALELO)...")
print("-" * 70)

inicio_total = time.time()

# Crear threads para ejecutar workers simultáneamente
threads = []
for i, asignacion in enumerate(asignaciones):
    thread = threading.Thread(target=ejecutar_worker, args=(asignacion, i))
    threads.append(thread)
    thread.start()

# Esperar a que todos los workers terminen
for thread in threads:
    thread.join()

fin_total = time.time()

print()
print("=" * 70)
print("FASE 2: Ensamblando video...")
print("-" * 70)
print()

try:
    import imageio

    # Verificar frames descargados
    frames_encontrados = sorted([f for f in os.listdir(CARPETA_FRAMES_LOCAL) if f.endswith('.png')])
    print(f"Frames encontrados: {len(frames_encontrados)}/{TOTAL_FRAMES}")

    if len(frames_encontrados) < TOTAL_FRAMES:
        print(f"Advertencia: Faltan {TOTAL_FRAMES - len(frames_encontrados)} frames")

    print("Cargando frames...")
    frames = []
    for i in range(TOTAL_FRAMES):
        frame_path = os.path.join(CARPETA_FRAMES_LOCAL, f"frame_{i:04d}.png")
        if os.path.exists(frame_path):
            frames.append(imageio.imread(frame_path))
            if (i + 1) % 10 == 0:
                print(f"Cargados: {i + 1}/{TOTAL_FRAMES} frames", end='\r', flush=True)

    print()
    print(f"Generando video con {len(frames)} frames...")

    video_path = os.path.join(CARPETA_RESULTADOS_LOCAL, "mandelbrot_zoom_animation.mp4")
    imageio.mimsave(video_path, frames, fps=10, codec='libx264', quality=8)

    print(f"✓ Video generado: {video_path}")
    print()

except ImportError:
    print("⚠  imageio no está instalado.")
    print("   Instala con: pip install imageio imageio-ffmpeg")
    print()
    print(f"   Los frames están disponibles en: {CARPETA_FRAMES_LOCAL}")
    print("   Puedes ensamblarlos manualmente o instalar imageio.")
    print()

# --- RESUMEN FINAL ---
print("=" * 70)
print("RESUMEN FINAL")
print("=" * 70)
print(f"⏱  Tiempo total: {fin_total - inicio_total:.2f} segundos")
print(f"🎞  Frames totales: {TOTAL_FRAMES}")
print(f"📐 Resolución: {WIDTH}x{HEIGHT}")
print(f"🔢 Iteraciones: {MAX_ITER}")
print(f"🔍 Zoom: {ZOOM_INICIAL}x → {ZOOM_FINAL}x")
print(f"💻 Workers utilizados: {len(HOSTS)}")
print()
print("Distribución del trabajo:")
for asig in asignaciones:
    tiempo_por_worker = (fin_total - inicio_total)  # Tiempo paralelo
    print(f"  • {asig['host']['nombre']}: {asig['total']} frames ({asig['total']/TOTAL_FRAMES*100:.1f}%)")
print()
print(f"📊 Trabajo del MASTER: 0% (solo coordinación)")
print(f"📊 Trabajo de WORKERS: 100% (cálculo paralelo)")
print()
print("Archivos generados:")
print(f"  • Frames individuales: {CARPETA_FRAMES_LOCAL}")
if os.path.exists(os.path.join(CARPETA_RESULTADOS_LOCAL, "mandelbrot_zoom_animation.mp4")):
    print(f"  • Video final: {os.path.join(CARPETA_RESULTADOS_LOCAL, 'mandelbrot_zoom_animation.mp4')}")
print("=" * 70)
print()
print("✅ CLUSTER FINALIZADO CON ÉXITO")
print()
print("💡 Para ver el video:")
print(f"   xdg-open {os.path.join(CARPETA_RESULTADOS_LOCAL, 'mandelbrot_zoom_animation.mp4')}")
print()