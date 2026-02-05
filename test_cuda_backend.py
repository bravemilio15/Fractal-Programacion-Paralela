"""
Test y Benchmark de Backend CUDA

Este script valida la implementación CUDA y compara rendimiento
entre los tres backends disponibles: Python, Numba y CUDA.
"""

import time
import sys
from PIL import Image
import numpy as np

print("=" * 60)
print("TEST DE BACKEND CUDA")
print("=" * 60)

# Test 1: Verificar CuPy y GPU
print("\n[TEST 1] Verificando GPU CUDA...")
try:
    import cupy as cp
    device = cp.cuda.Device(0)
    props = cp.cuda.runtime.getDeviceProperties(0)
    gpu_name = props['name'].decode()
    memory_gb = props['totalGlobalMem'] / (1024**3)
    
    print(f"✓ CuPy instalado correctamente")
    print(f"✓ GPU detectada: {gpu_name}")
    print(f"✓ Memoria total: {memory_gb:.2f} GB")
    print(f"✓ Compute Capability: {device.compute_capability}")
    
    CUDA_OK = True
except Exception as e:
    print(f"✗ CUDA no disponible: {e}")
    print("  → Los tests CUDA se saltarán")
    CUDA_OK = False

# Test 2: Importar renderers
print("\n[TEST 2] Importando renderers...")
try:
    from fractals import MandelbrotRenderer
    print("✓ MandelbrotRenderer (Python estándar)")
except Exception as e:
    print(f"✗ Error importando MandelbrotRenderer: {e}")
    sys.exit(1)

try:
    from fractals import MandelbrotOptimizedRenderer
    print("✓ Mandelbrot OptimizedRenderer (Numba)")
except Exception as e:
    print(f"✗ Error importando MandelbrotOptimizedRenderer: {e}")
    sys.exit(1)

if CUDA_OK:
    try:
        from fractals import MandelbrotCUDARenderer, CUDA_AVAILABLE
        if CUDA_AVAILABLE:
            print("✓ MandelbrotCUDARenderer (CUDA)")
        else:
            print("✗ MandelbrotCUDARenderer importado pero GPU no disponible")
            CUDA_OK = False
    except Exception as e:
        print(f"✗ Error importando MandelbrotCUDARenderer: {e}")
        CUDA_OK = False

# Configuración del test
print("\n[CONFIGURACIÓN DEL BENCHMARK]")
WIDTH = 800
HEIGHT = 600  
MAX_ITER = 100
X_MIN, X_MAX = -2.5, 1.0
Y_MIN, Y_MAX = -1.25, 1.25

print(f"Resolución: {WIDTH}x{HEIGHT}")
print(f"Iteraciones: {MAX_ITER}")
print(f"Región: [{X_MIN}, {X_MAX}] x [{Y_MIN}, {Y_MAX}]")

# Test 3: Renderizar con cada backend
print("\n[TEST 3] Renderizando frame de prueba...")

results = {}

# Backend 1: Python estándar (solo prueba rápida con resolución menor)
print("\n1. Python Estándar...")
try:
    renderer = MandelbrotRenderer()
    start = time.time()
    
    # Versión más pequeña para Python puro (muy lento)
    test_width, test_height = 200, 150
    iterations_std = np.zeros((test_height, test_width), dtype=np.int32)
    
    for row in range(test_height):
        y = Y_MIN + row * (Y_MAX - Y_MIN) / test_height
        for col in range(test_width):
            x = X_MIN + col * (X_MAX - X_MIN) / test_width
            c = complex(x, y)
            iterations_std[row, col] = renderer.calculate(c, MAX_ITER)
    
    elapsed = time.time() - start
    results['Python'] = elapsed
    print(f"   Tiempo: {elapsed:.2f}s ({test_width}x{test_height})")
    print(f"   Nota: Resolución reducida para evitar espera larga")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    results['Python'] = None

# Backend 2: Numba
print("\n2. Numba (CPU Optimizado)...")
try:
    renderer = MandelbrotOptimizedRenderer()
    start = time.time()
    iterations_numba = renderer.calculate_array(
        WIDTH, HEIGHT, X_MIN, X_MAX, Y_MIN, Y_MAX, MAX_ITER
    )
    elapsed = time.time() - start
    results['Numba'] = elapsed
    print(f"   Tiempo: {elapsed:.2f}s")
    
    # Convertir a imagen
    rgb_numba = renderer.render_to_rgb(iterations_numba, MAX_ITER)
    img_numba = Image.fromarray(rgb_numba, mode='RGB')
    img_numba.save('test_numba.png')
    print(f"   ✓ Guardado: test_numba.png")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    results['Numba'] = None

# Backend 3: CUDA
if CUDA_OK:
    print("\n3. CUDA (GPU)...")
    try:
        renderer = MandelbrotCUDARenderer(device_id=0)
        
        # Primer run (incluye JIT compilation)
        start = time.time()
        iterations_cuda = renderer.calculate_array(
            WIDTH, HEIGHT, X_MIN, X_MAX, Y_MIN, Y_MAX, MAX_ITER
        )
        first_run = time.time() - start
        print(f"   Primera ejecución (con JIT): {first_run:.2f}s")
        
        # Segundo run (ya compilado)
        start = time.time()
        iterations_cuda = renderer.calculate_array(
            WIDTH, HEIGHT, X_MIN, X_MAX, Y_MIN, Y_MAX, MAX_ITER
        )
        elapsed = time.time() - start
        results['CUDA'] = elapsed
        print(f"   Segunda ejecución: {elapsed:.2f}s")
        
        # Convertir a imagen
        rgb_cuda = renderer.render_to_rgb(iterations_cuda, MAX_ITER)
        img_cuda = Image.fromarray(rgb_cuda, mode='RGB')
        img_cuda.save('test_cuda.png')
        print(f"   ✓ Guardado: test_cuda.png")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        results['CUDA'] = None
else:
    print("\n3. CUDA (GPU)... SALTADO (no disponible)")
    results['CUDA'] = None

# Test 4: Comparar resultados
if results.get('Numba') is not None and results.get('CUDA') is not None:
    print("\n[TEST 4] Comparando resultados Numba vs CUDA...")
    try:
        diff = np.abs(iterations_numba - iterations_cuda)
        max_diff = np.max(diff)
        mean_diff = np.mean(diff)
        
        if max_diff == 0:
            print("✓ Resultados IDÉNTICOS (diferencia = 0)")
        elif max_diff <= 1:
            print(f"✓ Resultados casi idénticos (max diff = {max_diff})")
        else:
            print(f"⚠ Diferencias encontradas: max={max_diff}, mean={mean_diff:.4f}")
        
    except Exception as e:
        print(f"✗ Error comparando: {e}")

# Resumen de benchmark
print("\n" + "=" * 60)
print("RESUMEN DE BENCHMARK")
print("=" * 60)

if results.get('Numba') and results.get('CUDA'):
    speedup = results['Numba'] / results['CUDA']
    print(f"\nNumba (CPU):   {results['Numba']:.3f}s")
    print(f"CUDA (GPU):    {results['CUDA']:.3f}s")
    print(f"\nSpeedup:       {speedup:.2f}x")
    
    if speedup > 5:
        print("✓ CUDA es significativamente más rápido")
    elif speedup > 2:
        print("✓ CUDA es más rápido")
    elif speedup > 0.8:
        print("⚠ CUDA y Numba son comparables (overhead de transferencia)")
    else:
        print("⚠ Numba es más rápido (problema de configuración)")

elif results.get('Numba'):
    print(f"\nNumba (CPU):   {results['Numba']:.3f}s")
    print("CUDA:          No disponible")

print("\n" + "=" * 60)
print("CONCLUSIÓN:")
if CUDA_OK and results.get('CUDA') is not None:
    print("✓ CUDA está funcionando correctamente")
    print("✓ Integración completa")
    print("\nPróximo paso:")
    print("  1. Activar CUDA en config.yaml: use_cuda: true")
    print("  2. Ejecutar master.py con workers para probar cluster")
else:
    print("⚠ CUDA no está disponible o falló")
    print("  → El sistema usará Numba automáticamente")

print("=" * 60)
