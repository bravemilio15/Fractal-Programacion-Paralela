"""Tests unitarios para el módulo de fractales."""

import pytest
import numpy as np
from fractals import MandelbrotRenderer, MandelbrotOptimizedRenderer


class TestMandelbrotRenderer:
    """Tests para el renderizador estándar de Mandelbrot."""
    
    def test_punto_interior(self):
        """Punto dentro del conjunto debe alcanzar max_iter."""
        renderer = MandelbrotRenderer()
        c = complex(0, 0)  # Origen está dentro del conjunto
        result = renderer.calculate(c, 100)
        assert result == 100
    
    def test_punto_exterior(self):
        """Punto fuera del conjunto debe escapar rápido."""
        renderer = MandelbrotRenderer()
        c = complex(2, 2)  # Claramente fuera del conjunto
        result = renderer.calculate(c, 100)
        assert result < 100
    
    def test_color_negro_para_max_iter(self):
        """Puntos dentro del conjunto deben ser negros."""
        renderer = MandelbrotRenderer()
        color = renderer.get_color(100, 100)
        assert color == (0, 0, 0)
    
    def test_color_no_negro_para_escape(self):
        """Puntos que escapan deben tener color."""
        renderer = MandelbrotRenderer()
        color = renderer.get_color(50, 100)
        assert color != (0, 0, 0)
        # Verificar que los valores RGB están en rango válido
        assert all(0 <= c <= 255 for c in color)
    
    def test_nombre_renderer(self):
        """Verificar nombre del renderer."""
        renderer = MandelbrotRenderer()
        assert renderer.name == "Mandelbrot"


class TestMandelbrotOptimizedRenderer:
    """Tests para el renderizador optimizado de Mandelbrot."""
    
    def test_punto_interior(self):
        """Punto dentro del conjunto debe alcanzar max_iter."""
        renderer = MandelbrotOptimizedRenderer()
        c = complex(0, 0)
        result = renderer.calculate(c, 100)
        assert result == 100
    
    def test_punto_exterior(self):
        """Punto fuera del conjunto debe escapar rápido."""
        renderer = MandelbrotOptimizedRenderer()
        c = complex(2, 2)
        result = renderer.calculate(c, 100)
        assert result < 100
    
    def test_calculate_array_shape(self):
        """Array de salida debe tener dimensiones correctas."""
        renderer = MandelbrotOptimizedRenderer()
        width, height = 100, 80
        result = renderer.calculate_array(
            width, height,
            -2.0, 1.0,  # x_min, x_max
            -1.5, 1.5,  # y_min, y_max
            100
        )
        assert result.shape == (height, width)
    
    def test_calculate_array_dtype(self):
        """Array debe ser de tipo entero."""
        renderer = MandelbrotOptimizedRenderer()
        result = renderer.calculate_array(
            50, 50, -2.0, 1.0, -1.5, 1.5, 100
        )
        assert np.issubdtype(result.dtype, np.integer)
    
    def test_calculate_array_values_in_range(self):
        """Valores deben estar entre 0 y max_iter."""
        renderer = MandelbrotOptimizedRenderer()
        max_iter = 100
        result = renderer.calculate_array(
            50, 50, -2.0, 1.0, -1.5, 1.5, max_iter
        )
        assert np.all(result >= 0)
        assert np.all(result <= max_iter)
    
    def test_render_to_rgb_shape(self):
        """RGB array debe tener dimensiones correctas."""
        renderer = MandelbrotOptimizedRenderer()
        iterations = np.random.randint(0, 100, size=(50, 60))
        rgb = renderer.render_to_rgb(iterations, 100)
        assert rgb.shape == (50, 60, 3)
    
    def test_render_to_rgb_dtype(self):
        """RGB array debe ser uint8."""
        renderer = MandelbrotOptimizedRenderer()
        iterations = np.random.randint(0, 100, size=(50, 60))
        rgb = renderer.render_to_rgb(iterations, 100)
        assert rgb.dtype == np.uint8
    
    def test_render_to_rgb_values_in_range(self):
        """Valores RGB deben estar entre 0 y 255."""
        renderer = MandelbrotOptimizedRenderer()
        iterations = np.random.randint(0, 100, size=(50, 60))
        rgb = renderer.render_to_rgb(iterations, 100)
        assert np.all(rgb >= 0)
        assert np.all(rgb <= 255)
    
    def test_consistencia_con_version_estandar(self):
        """Versión optimizada debe dar resultados similares a estándar."""
        std_renderer = MandelbrotRenderer()
        opt_renderer = MandelbrotOptimizedRenderer()
        
        # Probar varios puntos
        test_points = [
            complex(0, 0),
            complex(-0.5, 0),
            complex(-1, 0),
            complex(0.25, 0),
        ]
        
        max_iter = 100
        for c in test_points:
            std_result = std_renderer.calculate(c, max_iter)
            opt_result = opt_renderer.calculate(c, max_iter)
            assert std_result == opt_result, f"Inconsistencia en punto {c}"


class TestRendererComparison:
    """Tests comparativos entre renderizadores."""
    
    def test_mismo_color_para_mismas_iteraciones(self):
        """Ambos renderizadores deben generar el mismo color."""
        std_renderer = MandelbrotRenderer()
        opt_renderer = MandelbrotOptimizedRenderer()
        
        for iterations in [0, 25, 50, 75, 100]:
            std_color = std_renderer.get_color(iterations, 100)
            opt_color = opt_renderer.get_color(iterations, 100)
            assert std_color == opt_color


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
