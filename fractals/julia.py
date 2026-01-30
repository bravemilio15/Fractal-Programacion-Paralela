"""Implementación del conjunto de Julia (versión estándar)."""

from typing import Tuple
from .base import FractalRenderer


class JuliaRenderer(FractalRenderer):
    """Renderizador del conjunto de Julia (versión estándar Python).
    
    El conjunto de Julia es un fractal donde la fórmula iterativa es:
    z(n+1) = z(n)^2 + c
    
    DIFERENCIA CLAVE vs Mandelbrot:
    - Mandelbrot: z0 = 0, c = punto evaluado (variable)
    - Julia: z0 = punto evaluado (variable), c = constante fija
    """
    
    def __init__(self, c_real: float = -0.7, c_imag: float = 0.27015):
        """
        Inicializa el renderizador de Julia con una constante c.
        
        Args:
            c_real: Parte real de la constante c
            c_imag: Parte imaginaria de la constante c
            
        Valores interesantes de c:
            (-0.7, 0.27015): "Douady's rabbit" - estructura dendrítica
            (-0.4, 0.6): "San Marco fractal" - simetría cuádruple
            (0.285, 0.01): "Siegel disk" - espirales suaves
            (-0.70176, -0.3842): Estructura de "dragón"
        """
        self.c = complex(c_real, c_imag)
    
    @property
    def name(self) -> str:
        return f"Julia (c={self.c.real:.4f}{self.c.imag:+.4f}i)"
    
    def calculate(self, z: complex, max_iter: int) -> int:
        """
        Calcula las iteraciones para un punto en el conjunto de Julia.
        
        Formula: z(n+1) = z(n)^2 + c, comenzando con z(0) = punto evaluado
        
        Args:
            z: Número complejo a evaluar (punto inicial z0)
            max_iter: Número máximo de iteraciones
        
        Returns:
            Número de iteraciones antes de escapar (o max_iter si no escapa)
        """
        for n in range(max_iter):
            if abs(z) > 2:
                return n
            z = z * z + self.c
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
        
        # Esquema de color psicodélico (mismo que Mandelbrot)
        ratio = iterations / max_iter
        r = int(255 * (ratio ** 0.5))
        g = int(255 * (ratio ** 0.3))
        b = int(255 * (1 - ratio ** 0.2))
        
        return (r, g, b)
