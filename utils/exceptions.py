"""Excepciones personalizadas para el sistema de renderizado."""


class RenderError(Exception):
    """Error durante el renderizado de un frame."""
    pass


class ClusterConnectionError(Exception):
    """Error de conexión al cluster Dask."""
    pass


class ConfigurationError(Exception):
    """Error en la configuración del sistema."""
    pass


class ValidationError(Exception):
    """Error de validación de parámetros."""
    pass


class CacheError(Exception):
    """Error en el sistema de caché."""
    pass
