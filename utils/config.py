"""Gestor de configuración del sistema."""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from .exceptions import ConfigurationError


class ConfigManager:
    """Gestor centralizado de configuración."""
    
    _instance: Optional['ConfigManager'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        """Singleton pattern para tener una única instancia."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa el gestor de configuración."""
        if not self._config:
            self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """
        Carga la configuración desde archivo YAML.
        
        Args:
            config_path: Ruta al archivo de configuración. Si es None, usa el default.
        
        Raises:
            ConfigurationError: Si no se puede cargar la configuración
        """
        if config_path is None:
            # Buscar config.yaml en directorio config/
            base_path = Path(__file__).parent.parent
            config_path = base_path / 'config' / 'config.yaml'
        
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise ConfigurationError(f"Archivo de configuración no encontrado: {config_path}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error al parsear YAML: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error al cargar configuración: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración usando notación de punto.
        
        Args:
            key: Clave en formato 'seccion.subseccion.valor'
            default: Valor por defecto si no existe la clave
        
        Returns:
            Valor de configuración o default
        
        Examples:
            >>> config = ConfigManager()
            >>> config.get('cluster.scheduler_port')
            8786
            >>> config.get('rendering.fps')
            15
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Establece un valor de configuración.
        
        Args:
            key: Clave en formato 'seccion.subseccion.valor'
            value: Nuevo valor
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self, config_path: Optional[str] = None) -> None:
        """
        Guarda la configuración actual en archivo YAML.
        
        Args:
            config_path: Ruta donde guardar. Si es None, usa el default.
        """
        if config_path is None:
            base_path = Path(__file__).parent.parent
            config_path = base_path / 'config' / 'config.yaml'
        
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            raise ConfigurationError(f"Error al guardar configuración: {e}")
    
    @property
    def all(self) -> Dict[str, Any]:
        """Retorna toda la configuración."""
        return self._config.copy()


# Instancia global
config = ConfigManager()
