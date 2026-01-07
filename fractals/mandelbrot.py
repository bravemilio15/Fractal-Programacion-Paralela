"""Implementación estándar del conjunto de Mandelbrot."""

from typing import Tuple
from .base import FractalRenderer


class MandelbrotRenderer(FractalRenderer):
    """Renderizador del conjunto de Mandelbrot (versión estándar Python)."""
    
    @property
    def name(self) -> str:
        return "Mandelbrot"
    
    def calculate(self, c: complex, max_iter: int) -> int:
        """
        Calcula iteraciones para el conjunto de Mandelbrot.
        
        Formula: z(n+1) = z(n)^2 + c, comenzando con z(0) = 0
        
        Args:
            c: Número complejo a evaluar
            max_iter: Número máximo de iteraciones
        
        Returns:
            Número de iteraciones antes de escapar
        """
        z = 0j
        for n in range(max_iter):
            if abs(z) > 2:
                return n
            z = z * z + c
        return max_iter
    
    def get_color(self, iterations: int, max_iter: int) -> Tuple[int, int, int]:
        """
        Genera color psicodélico basado en iteraciones.
        
        Args:
            iterations: Número de iteraciones calculadas
            max_iter: Número máximo de iteraciones
        
        Returns:
            Tupla RGB (0-255, 0-255, 0-255)
        """
        if iterations == max_iter:
            # Punto dentro del conjunto = negro
            return (0, 0, 0)
        
        # Esquema de color psicodélico
        ratio = iterations / max_iter
        r = int(255 * (ratio ** 0.5))
        g = int(255 * (ratio ** 0.3))
        b = int(255 * (1 - ratio ** 0.2))
        
        return (r, g, b)
