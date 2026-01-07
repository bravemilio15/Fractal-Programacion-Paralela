"""Clase base abstracta para renderizadores de fractales."""

from abc import ABC, abstractmethod
from typing import Tuple


class FractalRenderer(ABC):
    """Clase base para implementar diferentes tipos de fractales."""
    
    @abstractmethod
    def calculate(self, c: complex, max_iter: int) -> int:
        """
        Calcula el número de iteraciones para un punto complejo.
        
        Args:
            c: Número complejo a evaluar
            max_iter: Número máximo de iteraciones
        
        Returns:
            Número de iteraciones antes de escapar (o max_iter si no escapa)
        """
        pass
    
    @abstractmethod
    def get_color(self, iterations: int, max_iter: int) -> Tuple[int, int, int]:
        """
        Genera un color RGB basado en el número de iteraciones.
        
        Args:
            iterations: Número de iteraciones calculadas
            max_iter: Número máximo de iteraciones
        
        Returns:
            Tupla (R, G, B) con valores 0-255
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del fractal."""
        pass
