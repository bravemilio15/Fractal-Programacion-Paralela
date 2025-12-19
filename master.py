import time
import os
import sys
import socket
import threading
import imageio.v2 as imageio
from dask.distributed import Client, LocalCluster, as_completed

import dask
dask.config.set({
    "distributed.comm.timeouts.connect": "60s",  # Esperar más tiempo
    "distributed.comm.timeouts.tcp": "60s",      # Esperar más tiempo
    "distributed.worker.profile.interval": "2000ms", # Chequear estado menos seguido
})

# Importamos la tarea
try:
    from tareas import generar_frame_mandelbrot
except ImportError:
    print("❌ Error: Falta el archivo 'tareas.py'")
    sys.exit(1)

# --- CONFIGURACIÓN DE LA ANIMACIÓN ---
TOTAL_FRAMES = 50       
WIDTH = 800             
HEIGHT = 608          
MAX_ITER = 100          
X_CENTRO = -0.7436438870371587  # Un punto interesante del Mandelbrot
Y_CENTRO = 0.1318259042053119
ZOOM_INICIAL = 1.0      
ZOOM_FINAL = 15000.0     # Zoom muy profundo

CARPETA_SALIDA = "./frames_renderizados"
VIDEO_SALIDA = "mandelbrot_zoom.mp4"

# --- UTILIDADES UX ---
def obtener_ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        IP = s.getsockname()[0]
        s.close()
    except:
        IP = "127.0.0.1"
    return IP

def calcular_params_zoom(frame_num):
    """Calcula las coordenadas matemáticas para un frame específico"""
    t = frame_num / (TOTAL_FRAMES - 1) if TOTAL_FRAMES > 1 else 0
    # Interpolación exponencial para que el zoom se sienta suave
    zoom_actual = ZOOM_INICIAL * (ZOOM_FINAL / ZOOM_INICIAL) ** t
    
    ancho = 3.5 / zoom_actual
    alto = 2.5 / zoom_actual
    
    return {
        'frame_num': frame_num,
        'width': WIDTH, 'height': HEIGHT, 'max_iter': MAX_ITER,
        'x_min': X_CENTRO - ancho / 2,
        'x_max': X_CENTRO + ancho / 2,
        'y_min': Y_CENTRO - alto / 2,
        'y_max': Y_CENTRO + alto / 2
    }

def main():
    os.makedirs(CARPETA_SALIDA, exist_ok=True)
    ip = obtener_ip_local()
    
    print(f"\n🎬 MASTER DE RENDERIZADO - MANDELBROT ZOOM")
    print("="*60)
    
    # Iniciamos Cluster
    cluster = LocalCluster(host='0.0.0.0', scheduler_port=8786, n_workers=0, dashboard_address=':8787')
    client = Client(cluster)
    
    print(f"📡 IP Master: {ip}")
    print(f"📊 Dashboard: http://{ip}:8787")
    print("\n⏳ Esperando Workers...")

    # Loop de espera interactivo (UX: ENTER para iniciar)
    while True:
        workers = client.scheduler_info()['workers']
        sys.stdout.write(f"\r   🔌 Workers conectados: {len(workers)} (Presiona ENTER para iniciar render)")
        sys.stdout.flush()
        
        # Usamos un select con timeout para no bloquear el refresco de workers
        import select
        if sys.stdin in select.select([sys.stdin], [], [], 1)[0]:
            sys.stdin.readline() # Consumir el Enter
            if len(workers) > 0:
                break
            else:
                print("\n⚠️  ¡Necesitas al menos 1 worker conectado!")
    
    print(f"\n\n🚀 ¡INICIANDO RENDERIZADO DE {TOTAL_FRAMES} FRAMES!")
    start_time = time.time()
    
    # 1. Preparar lista de parámetros (Recetas)
    lista_tareas = [calcular_params_zoom(i) for i in range(TOTAL_FRAMES)]
    
    # 2. Enviar todo al cluster
    # Dask reparte automáticamente las recetas a quien esté libre
    futures = client.map(generar_frame_mandelbrot, lista_tareas)
    
    print(f"📨 Tareas enviadas. Recibiendo imágenes...")
    
    frames_guardados = 0
    
    # 3. Recibir resultados conforme llegan
    for future in as_completed(futures):
        try:
            num_frame, img_bytes = future.result()
            
            # Guardar en disco del Master
            nombre_archivo = f"frame_{num_frame:04d}.png"
            ruta_completa = os.path.join(CARPETA_SALIDA, nombre_archivo)
            
            with open(ruta_completa, "wb") as f:
                f.write(img_bytes)
            
            frames_guardados += 1
            
            # Barra de progreso
            porcentaje = int((frames_guardados / TOTAL_FRAMES) * 100)
            barra = "█" * (porcentaje // 2) + "░" * ((100 - porcentaje) // 2)
            print(f"\r   [{barra}] {porcentaje}% - Guardado: {nombre_archivo}", end="")
            
        except Exception as e:
            print(f"\n❌ Error en un frame: {e}")

    tiempo_render = time.time() - start_time
    print(f"\n\n✅ RENDERIZADO COMPLETO en {tiempo_render:.2f}s")
    
    # 4. Generar Video
    print("\n🎞  Ensamblando video MP4...")
    try:
        writer = imageio.get_writer(VIDEO_SALIDA, fps=15)
        
        for i in range(TOTAL_FRAMES):
            ruta = os.path.join(CARPETA_SALIDA, f"frame_{i:04d}.png")
            if os.path.exists(ruta):
                img = imageio.imread(ruta)
                writer.append_data(img)
            else:
                print(f"⚠️ Falta el frame {i}")
        
        writer.close()
        print(f"🏆 ¡VIDEO LISTO! -> {os.path.abspath(VIDEO_SALIDA)}")
        
    except Exception as e:
        print(f"❌ Error creando video (quizás falta ffmpeg): {e}")

    print("\n✅ PROCESO TERMINADO CORRECTAMENTE.")
    print(f"📁 Video guardado en: {os.path.abspath(VIDEO_SALIDA)}")
    
    try:
        input("\n👋 Presiona ENTER para cerrar el Cluster y salir...")
    except KeyboardInterrupt:
        print("\n\nCerrando forzosamente (Ctrl+C)...")
    
    # El cierre ya estaba, pero ahora está protegido
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