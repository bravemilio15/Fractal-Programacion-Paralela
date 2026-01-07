"""Sistema de logging estructurado para el proyecto."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    Configura y retorna un logger estructurado.
    
    Args:
        name: Nombre del logger (ej: 'master', 'worker', 'render')
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Ruta opcional para guardar logs en archivo
        console: Si True, también imprime logs en consola
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar duplicar handlers si ya existe
    if logger.handlers:
        return logger
    
    # Formato de logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para consola
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Handler para archivo
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Archivo siempre guarda DEBUG
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Loggers predefinidos para componentes principales
def get_master_logger() -> logging.Logger:
    """Retorna logger para el nodo master."""
    return setup_logger('master', log_file='logs/master.log')


def get_worker_logger() -> logging.Logger:
    """Retorna logger para nodos worker."""
    return setup_logger('worker', log_file='logs/worker.log')


def get_render_logger() -> logging.Logger:
    """Retorna logger para el motor de renderizado."""
    return setup_logger('render', log_file='logs/render.log')
