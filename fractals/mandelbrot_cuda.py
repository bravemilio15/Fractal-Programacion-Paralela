"""Implementación del conjunto de Mandelbrot con aceleración GPU (CUDA) usando CuPy.

VERSIÓN OPTIMIZADA: Usa kernel CUDA real para máximo uso de GPU.
"""

import numpy as np
from typing import Tuple, Optional
from .base import FractalRenderer

try:
    import cupy as cp
    from cupy import RawKernel
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False
    cp = None

# ============================================
# KERNEL CUDA REAL - Ejecuta TODO en GPU
# ============================================
MANDELBROT_KERNEL = """
extern "C" __global__
void mandelbrot_kernel(
    int* output,
    const int width,
    const int height,
    const float x_min,
    const float x_max,
    const float y_min,
    const float y_max,
    const int max_iter
) {
    // Calcular posición del thread
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    
    // Verificar límites
    if (col >= width || row >= height) return;
    
    // Mapear píxel a coordenada compleja
    float x0 = x_min + (float(col) / float(width)) * (x_max - x_min);
    float y0 = y_min + (float(row) / float(height)) * (y_max - y_min);
    
    // Variables de iteración
    float x = 0.0f;
    float y = 0.0f;
    int iter = 0;
    
    // Algoritmo de escape de Mandelbrot
    // TODO el cálculo ocurre DENTRO de la GPU
    while (x*x + y*y <= 4.0f && iter < max_iter) {
        float xtemp = x*x - y*y + x0;
        y = 2.0f*x*y + y0;
        x = xtemp;
        iter++;
    }
    
    // Guardar resultado
    output[row * width + col] = iter;
}
"""

JULIA_KERNEL = """
extern "C" __global__
void julia_kernel(
    int* output,
    const int width,
    const int height,
    const float x_min,
    const float x_max,
    const float y_min,
    const float y_max,
    const float c_real,
    const float c_imag,
    const int max_iter
) {
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    
    if (col >= width || row >= height) return;
    
    // Coordenada inicial Z = punto en el plano
    float x = x_min + (float(col) / float(width)) * (x_max - x_min);
    float y = y_min + (float(row) / float(height)) * (y_max - y_min);
    
    int iter = 0;
    
    // Julia: z = z² + c, donde c es constante
    while (x*x + y*y <= 4.0f && iter < max_iter) {
        float xtemp = x*x - y*y + c_real;
        y = 2.0f*x*y + c_imag;
        x = xtemp;
        iter++;
    }
    
    output[row * width + col] = iter;
}
"""


class MandelbrotCUDARenderer(FractalRenderer):
    """
    Renderizador del conjunto de Mandelbrot con aceleración GPU usando CUDA.
    
    VERSIÓN OPTIMIZADA: Usa kernel CUDA compilado que ejecuta TODO el cálculo
    en la GPU sin overhead de llamadas repetidas CPU↔GPU.
    
    Rendimiento esperado:
    - GPU Usage: 80-100% en renders 4K
    - 50-100x más rápido que CPU en frames grandes
    """
    
    # Kernels compilados (singleton)
    _mandelbrot_kernel = None
    _julia_kernel = None
    
    def __init__(self, device_id: int = 0):
        """
        Inicializa el renderizador GPU.
        """
        if not CUPY_AVAILABLE:
            raise ImportError(
                "CuPy no está instalado. Instálalo con: pip install cupy-cuda12x"
            )
        
        self.device_id = device_id
        
        # Verificar GPU
        try:
            with cp.cuda.Device(device_id):
                _ = cp.array([1.0])
            
            device = cp.cuda.Device(device_id)
            props = cp.cuda.runtime.getDeviceProperties(device_id)
            self.gpu_name = props['name'].decode()
            print(f"✓ GPU CUDA inicializada: {self.gpu_name}")
            
        except Exception as e:
            raise RuntimeError(f"No se pudo inicializar GPU {device_id}: {e}")
        
        # Compilar kernels CUDA (una sola vez)
        self._compile_kernels()
    
    def _compile_kernels(self):
        """Compila los kernels CUDA si no están compilados."""
        if MandelbrotCUDARenderer._mandelbrot_kernel is None:
            print("Compilando kernel CUDA Mandelbrot...")
            MandelbrotCUDARenderer._mandelbrot_kernel = cp.RawKernel(
                MANDELBROT_KERNEL, 'mandelbrot_kernel'
            )
            print("✓ Kernel Mandelbrot compilado")
        
        if MandelbrotCUDARenderer._julia_kernel is None:
            print("Compilando kernel CUDA Julia...")
            MandelbrotCUDARenderer._julia_kernel = cp.RawKernel(
                JULIA_KERNEL, 'julia_kernel'
            )
            print("✓ Kernel Julia compilado")
    
    @property
    def name(self) -> str:
        return "Mandelbrot CUDA (GPU)"
    
    def calculate(self, c: complex, max_iter: int) -> int:
        """Compatibilidad con interfaz base (no optimizado)."""
        z = 0j
        for n in range(max_iter):
            if abs(z) > 2:
                return n
            z = z * z + c
        return max_iter
    
    def get_color(self, iterations: int, max_iter: int) -> Tuple[int, int, int]:
        """Genera color."""
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
        max_iter: int,
        fractal_type: str = 'mandelbrot',
        c_real: float = -0.7,
        c_imag: float = 0.27015
    ) -> np.ndarray:
        """
        Calcula fractal usando KERNEL CUDA REAL.
        
        TODO el cálculo ocurre dentro de la GPU:
        - Sin loops Python
        - Sin overhead CPU↔GPU por iteración
        - Máximo uso de todos los CUDA cores
        """
        with cp.cuda.Device(self.device_id):
            # Array de salida en GPU
            output = cp.zeros((height, width), dtype=cp.int32)
            
            # Configuración de threads/blocks
            # 16x16 = 256 threads por bloque (óptimo)
            threads_per_block = (16, 16)
            blocks_x = (width + 15) // 16
            blocks_y = (height + 15) // 16
            grid = (blocks_x, blocks_y)
            
            # Ejecutar kernel según tipo de fractal
            if fractal_type == 'julia':
                MandelbrotCUDARenderer._julia_kernel(
                    grid, threads_per_block,
                    (output, width, height,
                     np.float32(x_min), np.float32(x_max),
                     np.float32(y_min), np.float32(y_max),
                     np.float32(c_real), np.float32(c_imag),
                     max_iter)
                )
            else:  # mandelbrot
                MandelbrotCUDARenderer._mandelbrot_kernel(
                    grid, threads_per_block,
                    (output, width, height,
                     np.float32(x_min), np.float32(x_max),
                     np.float32(y_min), np.float32(y_max),
                     max_iter)
                )
            
            # Sincronizar GPU
            cp.cuda.Stream.null.synchronize()
            
            # Transferir resultado a CPU
            result = cp.asnumpy(output)
        
        return result
    
    def render_to_rgb(
        self,
        iterations_array: np.ndarray,
        max_iter: int,
        progress_callback=None
    ) -> np.ndarray:
        """Convierte array de iteraciones a imagen RGB."""
        height, width = iterations_array.shape
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Normalizar iteraciones
        ratio = iterations_array.astype(float) / max_iter
        
        # Aplicar esquema de color vectorizado
        mask = iterations_array < max_iter
        
        rgb[:, :, 0] = np.where(mask, (255 * (ratio ** 0.5)).astype(np.uint8), 0)
        rgb[:, :, 1] = np.where(mask, (255 * (ratio ** 0.3)).astype(np.uint8), 0)
        rgb[:, :, 2] = np.where(mask, (255 * (1 - ratio ** 0.2)).astype(np.uint8), 0)
        
        if progress_callback:
            try:
                progress_callback(height, height, rgb)
            except:
                pass
        
        return rgb


def test_cuda_available() -> bool:
    """Verifica si CUDA está disponible y funcional."""
    if not CUPY_AVAILABLE:
        return False
    
    try:
        with cp.cuda.Device(0):
            _ = cp.array([1.0])
        return True
    except:
        return False


def get_gpu_info() -> Optional[dict]:
    """Obtiene información sobre la GPU disponible."""
    if not test_cuda_available():
        return None
    
    try:
        device = cp.cuda.Device(0)
        props = cp.cuda.runtime.getDeviceProperties(0)
        return {
            'device_id': 0,
            'name': props['name'].decode(),
            'compute_capability': device.compute_capability,
            'memory_total': props['totalGlobalMem'] / (1024**3),
        }
    except:
        return None
