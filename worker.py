import sys
import asyncio
import platform
import uuid
from dask.distributed import Worker
import dask

# Configuración Robustez WiFi
dask.config.set({
    "distributed.comm.timeouts.connect": "45s",
    "distributed.comm.timeouts.tcp": "45s",
})

async def iniciar_obrero(scheduler_ip):
    direccion_master = f"tcp://{scheduler_ip}:8786"
    nombre_pc = platform.node()
    id_unico = str(uuid.uuid4())[:4]
    nombre_final = f"Worker-{nombre_pc}-{id_unico}"
    
    print(f"\n👷 WORKER MANDELBROT (Python {sys.version.split()[0]})")
    print("="*50)
    print(f"🆔 ID: {nombre_final}")
    print(f"📡 Conectando a: {direccion_master}")
    
    try:
        async with Worker(direccion_master, name=nombre_final) as w:
            print(f"✅ CONECTADO. Esperando frames para renderizar...")
            await w.finished()     
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python worker.py <IP_MASTER> [--no-gui]")
        sys.exit(1)
    
    scheduler_ip = sys.argv[1]
    
    # Verificar si se solicita modo GUI o CLI
    if "--no-gui" in sys.argv:
        # Modo CLI original
        try:
            asyncio.run(iniciar_obrero(scheduler_ip))
        except KeyboardInterrupt:
            print("\nWorker apagado.")
    else:
        # Modo GUI
        try:
            from PyQt5.QtWidgets import QApplication
            from gui_worker import WorkerWindow
            
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
            
            window = WorkerWindow(scheduler_ip)
            window.show()
            
            sys.exit(app.exec_())
            
        except ImportError:
            print("ERROR: PyQt5 no esta instalado.")
            print("Instala con: pip install PyQt5")
            print("O ejecuta en modo CLI con: python worker.py <IP> --no-gui")
            sys.exit(1)