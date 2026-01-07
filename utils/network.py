"""Utilidades de red para el sistema distribuido."""

import socket
from typing import Optional


def get_local_ip() -> str:
    """
    Obtiene la dirección IP local de la máquina.
    
    Returns:
        IP local como string
    """
    try:
        # Crear socket UDP (no necesita conexión real)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def check_port_available(port: int, host: str = '0.0.0.0') -> bool:
    """
    Verifica si un puerto está disponible.
    
    Args:
        port: Número de puerto a verificar
        host: Host donde verificar
    
    Returns:
        True si el puerto está disponible
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def get_available_port(start_port: int = 8786, max_attempts: int = 100) -> Optional[int]:
    """
    Encuentra un puerto disponible comenzando desde start_port.
    
    Args:
        start_port: Puerto inicial para buscar
        max_attempts: Número máximo de intentos
    
    Returns:
        Puerto disponible o None si no se encuentra
    """
    for port in range(start_port, start_port + max_attempts):
        if check_port_available(port):
            return port
    return None
