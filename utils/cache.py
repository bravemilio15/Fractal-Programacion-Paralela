"""Sistema de caché para frames renderizados."""

import hashlib
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from .exceptions import CacheError
from .logger import setup_logger

logger = setup_logger('cache')


class FrameCache:
    """Sistema de caché para evitar re-renderizar frames idénticos."""
    
    def __init__(self, cache_dir: str = "./cache", max_size_mb: int = 1024):
        """
        Inicializa el sistema de caché.
        
        Args:
            cache_dir: Directorio donde guardar el caché
            max_size_mb: Tamaño máximo del caché en MB
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        logger.info(f"Caché inicializado en {self.cache_dir} (max: {max_size_mb}MB)")
    
    def get_cache_key(self, params: Dict[str, Any]) -> str:
        """
        Genera una clave única basada en los parámetros de renderizado.
        
        Args:
            params: Diccionario con parámetros de renderizado
        
        Returns:
            Hash MD5 único para estos parámetros
        """
        # Crear string único con parámetros relevantes
        key_parts = [
            str(params.get('width', 0)),
            str(params.get('height', 0)),
            str(params.get('max_iter', 0)),
            f"{params.get('x_min', 0):.10f}",
            f"{params.get('x_max', 0):.10f}",
            f"{params.get('y_min', 0):.10f}",
            f"{params.get('y_max', 0):.10f}",
        ]
        
        key_str = '_'.join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, params: Dict[str, Any]) -> Optional[bytes]:
        """
        Obtiene un frame del caché si existe.
        
        Args:
            params: Parámetros de renderizado
        
        Returns:
            Bytes de la imagen PNG o None si no está en caché
        """
        cache_key = self.get_cache_key(params)
        cache_file = self.cache_dir / f"{cache_key}.png"
        
        if cache_file.exists():
            try:
                logger.debug(f"Cache HIT para frame {params.get('frame_num', '?')}")
                return cache_file.read_bytes()
            except Exception as e:
                logger.warning(f"Error leyendo caché: {e}")
                return None
        
        logger.debug(f"Cache MISS para frame {params.get('frame_num', '?')}")
        return None
    
    def set(self, params: Dict[str, Any], img_bytes: bytes) -> None:
        """
        Guarda un frame en el caché.
        
        Args:
            params: Parámetros de renderizado
            img_bytes: Bytes de la imagen PNG
        """
        cache_key = self.get_cache_key(params)
        cache_file = self.cache_dir / f"{cache_key}.png"
        
        try:
            cache_file.write_bytes(img_bytes)
            logger.debug(f"Frame {params.get('frame_num', '?')} guardado en caché")
            
            # Verificar tamaño del caché
            self._check_cache_size()
            
        except Exception as e:
            logger.error(f"Error guardando en caché: {e}")
    
    def _check_cache_size(self) -> None:
        """Verifica el tamaño del caché y limpia si es necesario."""
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob('*.png'))
        
        if total_size > self.max_size_bytes:
            logger.warning(f"Caché excede límite ({total_size / 1024 / 1024:.1f}MB). Limpiando...")
            self.clear_old_files()
    
    def clear_old_files(self, keep_newest: int = 100) -> None:
        """
        Limpia archivos antiguos del caché.
        
        Args:
            keep_newest: Número de archivos más recientes a mantener
        """
        files = sorted(
            self.cache_dir.glob('*.png'),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        # Eliminar archivos antiguos
        for old_file in files[keep_newest:]:
            try:
                old_file.unlink()
                logger.debug(f"Eliminado del caché: {old_file.name}")
            except Exception as e:
                logger.error(f"Error eliminando {old_file}: {e}")
    
    def clear_all(self) -> None:
        """Limpia todo el caché."""
        try:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Caché completamente limpiado")
        except Exception as e:
            raise CacheError(f"Error limpiando caché: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del caché.
        
        Returns:
            Diccionario con estadísticas
        """
        files = list(self.cache_dir.glob('*.png'))
        total_size = sum(f.stat().st_size for f in files)
        
        return {
            'num_files': len(files),
            'total_size_mb': total_size / 1024 / 1024,
            'max_size_mb': self.max_size_bytes / 1024 / 1024,
            'usage_percent': (total_size / self.max_size_bytes) * 100 if self.max_size_bytes > 0 else 0
        }
