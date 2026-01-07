"""Implementación optimizada del conjunto de Mandelbrot con NumPy y Numba."""

import numpy as np
from typing import Tuple
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


class MandelbrotOptimizedRenderer(FractalRenderer):
    """
    Renderizador optimizado del conjunto de Mandelbrot.
    
    Utiliza NumPy para operaciones vectorizadas y Numba JIT para compilación.
    Ganancia de rendimiento esperada: 10-100x más rápido que versión estándar.
    """
    
    def __init__(self):
        """Inicializa el renderizador optimizado."""
        self.use_numba = NUMBA_AVAILABLE
        if not self.use_numba:
            print("⚠️  Numba no disponible. Usando NumPy puro (más lento).")
    
    @property
    def name(self) -> str:
        return "Mandelbrot Optimizado" + (" (Numba)" if self.use_numba else " (NumPy)")
    
    def calculate(self, c: complex, max_iter: int) -> int:
        """
        Calcula iteraciones para un punto (compatibilidad con interfaz base).
        
        Nota: Este método es para compatibilidad. Para mejor rendimiento,
        usar calculate_array() que procesa múltiples puntos a la vez.
        """
        z = 0j
        for n in range(max_iter):
            if abs(z) > 2:
                return n
            z = z * z + c
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
        Calcula Mandelbrot para una grilla completa (OPTIMIZADO).
        
        Args:
            width: Ancho en píxeles
            height: Alto en píxeles
            x_min, x_max: Rango en eje X
            y_min, y_max: Rango en eje Y
            max_iter: Iteraciones máximas
        
        Returns:
            Array 2D con número de iteraciones por píxel
        """
        if self.use_numba:
            return self._calculate_numba(width, height, x_min, x_max, y_min, y_max, max_iter)
        else:
            return self._calculate_numpy(width, height, x_min, x_max, y_min, y_max, max_iter)
    
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
        # Crear grilla de coordenadas complejas
        x = np.linspace(x_min, x_max, width)
        y = np.linspace(y_min, y_max, height)
        X, Y = np.meshgrid(x, y)
        C = X + 1j * Y
        
        # Inicializar arrays
        Z = np.zeros_like(C, dtype=complex)
        M = np.zeros(C.shape, dtype=np.int32)
        
        # Algoritmo vectorizado
        for i in range(max_iter):
            # Máscara de puntos que no han escapado
            mask = np.abs(Z) <= 2
            
            # Actualizar solo puntos activos
            Z[mask] = Z[mask]**2 + C[mask]
            M[mask] = i
        
        return M
    
    @staticmethod
    @jit(nopython=True, parallel=True, cache=True)
    def _calculate_numba_kernel(
        width: int,
        height: int,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        max_iter: int
    ) -> np.ndarray:
        """
        Kernel Numba JIT compilado (50-100x más rápido que Python puro).
        
        Usa paralelización automática con prange.
        """
        result = np.zeros((height, width), dtype=np.int32)
        
        dx = (x_max - x_min) / width
        dy = (y_max - y_min) / height
        
        # Paralelización automática por filas
        for row in prange(height):
            y = y_min + row * dy
            
            for col in range(width):
                x = x_min + col * dx
                c = complex(x, y)
                
                z = 0j
                for n in range(max_iter):
                    if abs(z) > 2:
                        result[row, col] = n
                        break
                    z = z * z + c
                else:
                    result[row, col] = max_iter
        
        return result
    
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
        return self._calculate_numba_kernel(width, height, x_min, x_max, y_min, y_max, max_iter)
    
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
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Normalizar iteraciones
        ratio = iterations_array.astype(float) / max_iter
        
        # Aplicar esquema de color vectorizado
        mask = iterations_array < max_iter
        
        rgb[:, :, 0] = np.where(mask, (255 * (ratio ** 0.5)).astype(np.uint8), 0)  # R
        rgb[:, :, 1] = np.where(mask, (255 * (ratio ** 0.3)).astype(np.uint8), 0)  # G
        rgb[:, :, 2] = np.where(mask, (255 * (1 - ratio ** 0.2)).astype(np.uint8), 0)  # B
        
        # Llamar callback con imagen completa al final
        if progress_callback:
            try:
                progress_callback(height, height, rgb)
            except:
                pass
        
        return rgb
    
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
            lines_per_update: Número de líneas entre actualizaciones
        
        Returns:
            Array 3D (height, width, 3) con valores RGB
        """
        height, width = iterations_array.shape
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Normalizar iteraciones
        ratio = iterations_array.astype(float) / max_iter
        
        # Aplicar esquema de color fila por fila (como realmente se genera)
        mask = iterations_array < max_iter
        
        # Procesar línea por línea para permitir callbacks progresivos
        for row in range(height):
            # Colorizar esta línea
            rgb[row, :, 0] = np.where(mask[row, :], (255 * (ratio[row, :] ** 0.5)).astype(np.uint8), 0)  # R
            rgb[row, :, 1] = np.where(mask[row, :], (255 * (ratio[row, :] ** 0.3)).astype(np.uint8), 0)  # G
            rgb[row, :, 2] = np.where(mask[row, :], (255 * (1 - ratio[row, :] ** 0.2)).astype(np.uint8), 0)  # B
            
            # Llamar callback cada N líneas
            if progress_callback and (row % lines_per_update == 0 or row == height - 1):
                try:
                    progress_callback(row + 1, height, rgb.copy())
                except:
                    pass
        
        return rgb

