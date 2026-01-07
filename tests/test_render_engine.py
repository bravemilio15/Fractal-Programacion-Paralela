"""Tests para el módulo de tareas de renderizado."""

import pytest
from PIL import Image
import io
from tareas import (
    generar_frame_mandelbrot,
    validate_params,
    calcular_mandelbrot,
    obtener_color
)
from utils.exceptions import ValidationError, RenderError


class TestValidateParams:
    """Tests para validación de parámetros."""
    
    def test_params_validos(self):
        """Parámetros válidos no deben lanzar excepción."""
        params = {
            'frame_num': 0,
            'width': 100,
            'height': 100,
            'max_iter': 50,
            'x_min': -2.0,
            'x_max': 1.0,
            'y_min': -1.5,
            'y_max': 1.5
        }
        validate_params(params)  # No debe lanzar excepción
    
    def test_falta_parametro_requerido(self):
        """Debe lanzar error si falta parámetro."""
        params = {
            'frame_num': 0,
            'width': 100,
            # Falta height
        }
        with pytest.raises(ValidationError):
            validate_params(params)
    
    def test_dimensiones_negativas(self):
        """Debe rechazar dimensiones negativas."""
        params = {
            'frame_num': 0,
            'width': -100,
            'height': 100,
            'max_iter': 50,
            'x_min': -2.0,
            'x_max': 1.0,
            'y_min': -1.5,
            'y_max': 1.5
        }
        with pytest.raises(ValidationError):
            validate_params(params)
    
    def test_coordenadas_invalidas(self):
        """Debe rechazar x_min >= x_max."""
        params = {
            'frame_num': 0,
            'width': 100,
            'height': 100,
            'max_iter': 50,
            'x_min': 1.0,
            'x_max': -2.0,  # Inválido
            'y_min': -1.5,
            'y_max': 1.5
        }
        with pytest.raises(ValidationError):
            validate_params(params)


class TestGenerarFrameMandelbrot:
    """Tests para generación de frames."""
    
    def test_generar_frame_basico(self):
        """Debe generar un frame válido."""
        params = {
            'frame_num': 0,
            'width': 50,
            'height': 50,
            'max_iter': 50,
            'x_min': -2.0,
            'x_max': 1.0,
            'y_min': -1.5,
            'y_max': 1.5,
            'use_optimized': False,  # Usar versión estándar para test
            'compress': False  # No comprimir en tests
        }
        
        frame_num, img_bytes = generar_frame_mandelbrot(params)
        
        assert frame_num == 0
        assert len(img_bytes) > 0
        assert img_bytes.startswith(b'\x89PNG')  # PNG magic number
    
    def test_frame_es_imagen_valida(self):
        """Los bytes deben ser una imagen PNG válida."""
        params = {
            'frame_num': 1,
            'width': 100,
            'height': 80,
            'max_iter': 50,
            'x_min': -2.0,
            'x_max': 1.0,
            'y_min': -1.5,
            'y_max': 1.5,
            'use_optimized': False,
            'compress': False
        }
        
        frame_num, img_bytes = generar_frame_mandelbrot(params)
        
        # Verificar que se puede abrir como imagen
        img = Image.open(io.BytesIO(img_bytes))
        assert img.size == (100, 80)
        assert img.mode == 'RGB'
    
    def test_version_optimizada(self):
        """Versión optimizada debe funcionar."""
        params = {
            'frame_num': 0,
            'width': 100,
            'height': 100,
            'max_iter': 50,
            'x_min': -2.0,
            'x_max': 1.0,
            'y_min': -1.5,
            'y_max': 1.5,
            'use_optimized': True,
            'compress': False
        }
        
        frame_num, img_bytes = generar_frame_mandelbrot(params)
        
        assert frame_num == 0
        assert len(img_bytes) > 0
        assert img_bytes.startswith(b'\x89PNG')


class TestLegacyFunctions:
    """Tests para funciones legacy."""
    
    def test_calcular_mandelbrot_punto_interior(self):
        """Función legacy debe funcionar."""
        c = complex(0, 0)
        result = calcular_mandelbrot(c, 100)
        assert result == 100
    
    def test_obtener_color_negro(self):
        """Función legacy de color debe funcionar."""
        color = obtener_color(100, 100)
        assert color == (0, 0, 0)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
