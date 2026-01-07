"""Tests para el gestor de configuración."""

import pytest
import tempfile
import os
from pathlib import Path
from utils.config import ConfigManager
from utils.exceptions import ConfigurationError


class TestConfigManager:
    """Tests para el gestor de configuración."""
    
    def test_singleton_pattern(self):
        """Debe retornar la misma instancia."""
        config1 = ConfigManager()
        config2 = ConfigManager()
        assert config1 is config2
    
    def test_get_valor_simple(self):
        """Debe obtener valores simples."""
        config = ConfigManager()
        # Estos valores vienen del config.yaml
        fps = config.get('rendering.fps')
        assert fps is not None
    
    def test_get_valor_default(self):
        """Debe retornar default si no existe."""
        config = ConfigManager()
        valor = config.get('clave.inexistente', 'default')
        assert valor == 'default'
    
    def test_set_valor(self):
        """Debe poder establecer valores."""
        config = ConfigManager()
        config.set('test.valor', 123)
        assert config.get('test.valor') == 123
    
    def test_get_nested_value(self):
        """Debe obtener valores anidados."""
        config = ConfigManager()
        # Verificar que puede acceder a valores anidados
        timeout = config.get('cluster.timeouts.connect')
        assert timeout is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
