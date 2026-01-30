"""Implementación optimizada del conjunto de Julia con NumPy y Numba."""

import numpy as np
from typing import Tuple, Optional, Callable
from .base import FractalRenderer

try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Fallback decorador que no hace nada
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range


class JuliaOptimizedRenderer(FractalRenderer):
    """Renderizador optimizado del conjunto de Julia.
    
    Utiliza NumPy para operaciones vectorizadas y Numba JIT para compilación.
    Puede ser 10-100x más rápido que la versión Python puro.
    """
    
    def __init__(self, c_real: float = -0.7, c_imag: float = 0.27015):
        """Inicializa el renderizador optimizado."""
        self.c = complex(c_real, c_imag)
        self.using_numba = NUMBA_AVAILABLE
    
    @property
    def name(self) -> str:
        mode = "Numba" if self.using_numba else "NumPy"
        return f"Julia Optimized ({mode}, c={self.c.real:.4f}{self.c.imag:+.4f}i)"
    
    def calculate(self, z: complex, max_iter: int) -> int:
        """
        Calcula iteraciones para un punto (compatibilidad con interfaz base).
        
        Nota: Este método es para compatibilidad. Para mejor rendimiento,
        usar calculate_array() que procesa múltiples puntos a la vez.
        """
        for n in range(max_iter):
            if abs(z) > 2:
                return n
            z = z * z + self.c
        return max_iter
    
    def get_color(self, iterations: int, max_iter: int) -> Tuple[int, int, int]:
        """Genera color (mismo esquema que versión estándar)."""
        if iterations == max_iter:
            return (0, 0, 0)
        
        ratio = iterations / max_iter
        r = int(255 * (ratio ** 0.5))
        g = int(255 * (ratio ** 0.3))
        b = int(255 * (1 - ratio ** 0.2))
        
        return (r, g, b)
    
    def calculate_array(
        self,
        width: int,
        height: int,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        max_iter: int
    ) -> np.ndarray:
        """
        Calcula Julia para una grilla completa (OPTIMIZADO).
        
        Args:
            width: Ancho en píxeles
            height: Alto en píxeles
            x_min, x_max: Rango en eje X
            y_min, y_max: Rango en eje Y
            max_iter: Iteraciones máximas
        
        Returns:
            Array 2D (height, width) con iteraciones
        """
        if self.using_numba:
            return self._calculate_numba(
                width, height, x_min, x_max, y_min, y_max, max_iter
            )
        else:
            return self._calculate_numpy(
                width, height, x_min, x_max, y_min, y_max, max_iter
            )
    
    def _calculate_numpy(
        self,
        width: int,
        height: int,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        max_iter: int
    ) -> np.ndarray:
        """Versión NumPy vectorizada (10-20x más rápida que Python puro)."""
        x = np.linspace(x_min, x_max, width)
        y = np.linspace(y_min, y_max, height)
        X, Y = np.meshgrid(x, y)
        
        # DIFERENCIA CLAVE: z0 = punto (no c=punto como en Mandelbrot)
        Z = X + 1j * Y
        iterations = np.zeros(Z.shape, dtype=int)
        
        for i in range(max_iter):
            mask = np.abs(Z) <= 2
            Z[mask] = Z[mask]**2 + self.c  # c es constante
            iterations[mask] = i
        
        return iterations
    
    @staticmethod
    @jit(nopython=True, parallel=True, cache=True)
    def _calculate_numba_kernel(
        width: int,
        height: int,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        max_iter: int,
        c_real: float,
        c_imag: float
    ):
        """
        Kernel Numba JIT compilado (50-100x más rápido que Python puro).
        
        Usa paralelización automática con prange.
        """
        iterations = np.zeros((height, width), dtype=np.int32)
        
        x_step = (x_max - x_min) / width
        y_step = (y_max - y_min) / height
        
        for row in prange(height):
            y = y_min + row * y_step
            for col in range(width):
                x = x_min + col * x_step
                
                # DIFERENCIA CLAVE: z0 = punto (no c=punto)
                z_real = x
                z_imag = y
                
                for n in range(max_iter):
                    z_abs_sq = z_real * z_real + z_imag * z_imag
                    if z_abs_sq > 4:
                        iterations[row, col] = n
                        break
                    
                    # z = z^2 + c (c es constante)
                    new_real = z_real * z_real - z_imag * z_imag + c_real
                    new_imag = 2 * z_real * z_imag + c_imag
                    z_real = new_real
                    z_imag = new_imag
                else:
                    iterations[row, col] = max_iter
        
        return iterations
    
    def _calculate_numba(
        self,
        width: int,
        height: int,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        max_iter: int
    ) -> np.ndarray:
        """Wrapper para versión Numba."""
        return self._calculate_numba_kernel(
            width, height, x_min, x_max, y_min, y_max, max_iter,
            self.c.real, self.c.imag
        )
    
    def render_to_rgb(
        self,
        iterations_array: np.ndarray,
        max_iter: int,
        progress_callback=None
    ) -> np.ndarray:
        """
        Convierte array de iteraciones a imagen RGB.
        
        Args:
            iterations_array: Array 2D con iteraciones
            max_iter: Iteraciones máximas
            progress_callback: Callback opcional (row, total_rows, partial_rgb)
        
        Returns:
            Array 3D (height, width, 3) con valores RGB
        """
        height, width = iterations_array.shape
        rgb_array = np.zeros((height, width, 3), dtype=np.uint8)
        
        for row in range(height):
            for col in range(width):
                iters = iterations_array[row, col]
                rgb_array[row, col] = self.get_color(iters, max_iter)
            
            # Callback progresivo
            if progress_callback and row % 50 == 0 and row > 0:
                try:
                    progress_callback(row, height, rgb_array.copy())
                except:
                    pass
        
        return rgb_array
    
    def render_to_rgb_progressive(
        self,
        iterations_array: np.ndarray,
        max_iter: int,
        progress_callback=None,
        lines_per_update: int = 10
    ) -> np.ndarray:
        """
        Convierte array de iteraciones a imagen RGB con actualizaciones progresivas.
        
        Esta versión llama al callback cada N líneas para permitir visualización
        en tiempo real del proceso de renderizado.
        
        Args:
            iterations_array: Array 2D con iteraciones
            max_iter: Iteraciones máximas
            progress_callback: Callback (current_row, total_rows, partial_rgb)
            lines_per_update: Líneas a renderizar entre callbacks
        
        Returns:
            Array 3D (height, width, 3) con valores RGB
        """
        height, width = iterations_array.shape
        rgb_array = np.zeros((height, width, 3), dtype=np.uint8)
        
        for row in range(height):
            for col in range(width):
                iters = iterations_array[row, col]
                rgb_array[row, col] = self.get_color(iters, max_iter)
            
            # Callback progresivo
            if progress_callback and row % lines_per_update == 0 and row > 0:
                try:
                    progress_callback(row, height, rgb_array.copy())
                except:
                    pass
        
        # Callback final
        if progress_callback:
            try:
                progress_callback(height, height, rgb_array)
            except:
                pass
        
        return rgb_array
