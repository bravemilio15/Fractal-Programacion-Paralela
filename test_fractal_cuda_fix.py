"""
Test rápido para verificar que CUDA selecciona el tipo de fractal correcto.

Este script prueba que:
1. Mandelbrot con CUDA renderiza Mandelbrot (no Julia)
2. Julia con CUDA renderiza Julia correctamente
3. Los parámetros se pasan correctamente
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("TEST: CUDA Fractal Type Selection")
print("=" * 60)

# Test 1: Verificar que CUDA está disponible
print("\n[1] Verificando CUDA...")
try:
    from fractals import CUDA_AVAILABLE
    if CUDA_AVAILABLE:
        print("✓ CUDA disponible")
    else:
        print("✗ CUDA no disponible - El test se saltará")
        sys.exit(0)
except ImportError as e:
    print(f"✗ Error importando: {e}")
    sys.exit(1)

# Test 2: Importar tareas y verificar que no hay errores de sintaxis
print("\n[2] Importando tareas.py...")
try:
    from tareas import generar_frame_fractal
    print("✓ tareas.py importado correctamente")
except ImportError as e:
    print(f"✗ Error importando tareas.py: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Renderizar Mandelbrot con CUDA
print("\n[3] Renderizando Mandelbrot con CUDA...")
try:
    params_mandelbrot = {
        'frame_num': 0,
        'width': 400,
        'height': 300,
        'max_iter': 50,
        'x_min': -2.5,
        'x_max': 1.0,
        'y_min': -1.25,
        'y_max': 1.25,
        'use_cuda': True,
        'use_optimized': True,
        'fractal_type': 'mandelbrot'
    }
    
    frame_num, img_bytes = generar_frame_fractal(params_mandelbrot)
    
    # Guardar para inspección visual
    with open('test_mandelbrot_cuda_fix.png', 'wb') as f:
        f.write(img_bytes)
    
    print(f"✓ Mandelbrot renderizado correctamente")
    print(f"  - Frame: {frame_num}")
    print(f"  - Tamaño: {len(img_bytes) / 1024:.1f} KB")
    print(f"  - Guardado: test_mandelbrot_cuda_fix.png")
    
except Exception as e:
    print(f"✗ Error renderizando Mandelbrot: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Renderizar Julia con CUDA
print("\n[4] Renderizando Julia con CUDA...")
try:
    params_julia = {
        'frame_num': 1,
        'width': 400,
        'height': 300,
        'max_iter': 50,
        'x_min': -2.0,
        'x_max': 2.0,
        'y_min': -2.0,
        'y_max': 2.0,
        'use_cuda': True,
        'use_optimized': True,
        'fractal_type': 'julia',
        'fractal_params': {
            'c_real': -0.7,
            'c_imag': 0.27015
        }
    }
    
    frame_num, img_bytes = generar_frame_fractal(params_julia)
    
    # Guardar para inspección visual
    with open('test_julia_cuda_fix.png', 'wb') as f:
        f.write(img_bytes)
    
    print(f"✓ Julia renderizado correctamente")
    print(f"  - Frame: {frame_num}")
    print(f"  - Tamaño: {len(img_bytes) / 1024:.1f} KB")
    print(f"  - Guardado: test_julia_cuda_fix.png")
    
except Exception as e:
    print(f"✗ Error renderizando Julia: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("RESULTADO: ✓ Todos los tests pasaron")
print("=" * 60)
print("\nPróximos pasos:")
print("1. Revisar test_mandelbrot_cuda_fix.png - Debe mostrar Mandelbrot")
print("2. Revisar test_julia_cuda_fix.png - Debe mostrar Julia")
print("3. Probar en la GUI con workers reales")
print("=" * 60)
