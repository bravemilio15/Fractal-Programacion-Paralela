"""
Nodo Worker para renderizado distribuido de fractales de Mandelbrot.

Este script se conecta al master y ejecuta tareas de renderizado de frames.
"""

import sys
import asyncio
import platform
import uuid
from dask.distributed import Worker
import dask

# Importar nueva infraestructura
from utils.config import config
from utils.logger import get_worker_logger

# Logger
logger = get_worker_logger()

# Configurar Dask desde config.yaml
dask.config.set({
    "distributed.comm.timeouts.connect": config.get('cluster.timeouts.connect', '45s'),
    "distributed.comm.timeouts.tcp": config.get('cluster.timeouts.tcp', '45s'),
})


async def iniciar_obrero(scheduler_ip: str) -> None:
    """
    Inicia el worker y se conecta al scheduler.
    
    Args:
        scheduler_ip: Dirección IP del scheduler/master
    """
    scheduler_port = config.get('cluster.scheduler_port', 8786)
    direccion_master = f"tcp://{scheduler_ip}:{scheduler_port}"
    
    nombre_pc = platform.node()
    id_unico = str(uuid.uuid4())[:4]
    nombre_final = f"Worker-{nombre_pc}-{id_unico}"
    
    logger.info("="*50)
    logger.info(f"WORKER MANDELBROT (Python {sys.version.split()[0]})")
    logger.info("="*50)
    logger.info(f"ID: {nombre_final}")
    
    while True:
        try:
            logger.info(f"Conectando al scheduler en {direccion_master}...")
            
            async with Worker(direccion_master, name=nombre_final) as w:
                logger.info(f"Worker '{nombre_final}' conectado exitosamente")
                logger.info(f"Dirección local: {w.address}")
                
                # Mantener worker activo
                await w.finished()
                
        except (OSError, asyncio.TimeoutError, Exception) as e:
            logger.warning(f"Conexión perdida o error: {e}")
            logger.info("Reintentando conexión en 5 segundos...")
            await asyncio.sleep(5)  # Esperar antes de reintentar
            continue
        
        # Si llegamos aquí, el worker terminó normalmente
        logger.info("Worker finalizado")
        break


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