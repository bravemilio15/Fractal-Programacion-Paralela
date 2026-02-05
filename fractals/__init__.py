"""
Módulo de renderizadores de fractales.

Contiene implementaciones de diferentes conjuntos fractales con
múltiples backends de optimización:
- Estándar: Python puro
- Optimizado: NumPy + Numba (CPU multi-core)
- CUDA: GPU NVIDIA (opcional, requiere CuPy)
"""

from .base import FractalRenderer
from .mandelbrot import MandelbrotRenderer
from .mandelbrot_optimized import MandelbrotOptimizedRenderer
from .julia import JuliaRenderer
from .julia_optimized import JuliaOptimizedRenderer

# CUDA renderer (opcional - requiere GPU NVIDIA + CuPy)
try:
    from .mandelbrot_cuda import MandelbrotCUDARenderer, test_cuda_available, get_gpu_info
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False
    MandelbrotCUDARenderer = None
    test_cuda_available = lambda: False
    get_gpu_info = lambda: None

__all__ = [
    'FractalRenderer',
    'MandelbrotRenderer',
    'MandelbrotOptimizedRenderer',
    'JuliaRenderer',
    'JuliaOptimizedRenderer',
    'MandelbrotCUDARenderer',
    'CUDA_AVAILABLE',
    'test_cuda_available',
    'get_gpu_info',
]
