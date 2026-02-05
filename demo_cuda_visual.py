"""
Demostración Visual de CUDA - Renderizado en Tiempo Real

Este script renderiza fractales mostrando:
1. Información detallada de GPU en tiempo real
2. Indicador visual de backend usado (CUDA/Numba)
3. Comparación lado a lado de resultados
4. Métricas de rendimiento
"""

import time
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt

print("=" * 70)
print(" DEMOSTRACIÓN VISUAL CUDA - RENDERIZADO DE FRACTALES ".center(70, "="))
print("=" * 70)

# Verificar CUDA disponible
print("\n[PASO 1] Verificando GPU CUDA...")
try:
    import cupy as cp
    from fractals import MandelbrotCUDARenderer, get_gpu_info
    
    gpu_info = get_gpu_info()
    if gpu_info:
        device = cp.cuda.Device(0)
        mem_info = device.mem_info
        
        print(f"\n✓ GPU DETECTADA:")
        print(f"  Nombre: {gpu_info['name']}")
        print(f"  Memoria total: {gpu_info['memory_total']:.2f} GB")
        print(f"  Memoria libre: {mem_info[0] / (1024**3):.2f} GB")
        print(f"  Compute Capability: {gpu_info['compute_capability']}")
        
        CUDA_AVAILABLE = True
    else:
        print("\n✗ GPU info no disponible")
        CUDA_AVAILABLE = False
        
except Exception as e:
    print(f"\n✗ CUDA no disponible: {e}")
    print("  → Solo se usará Numba")
    CUDA_AVAILABLE = False

# Importar renderers
print("\n[PASO 2] Cargando renderers...")
from fractals import MandelbrotRenderer, MandelbrotOptimizedRenderer

print("  ✓ MandelbrotRenderer (Python puro)")
print("  ✓ MandelbrotOptimizedRenderer (Numba)")
if CUDA_AVAILABLE:
    print("  ✓ MandelbrotCUDARenderer (CUDA GPU)")

# Configuración del render
print("\n[PASO 3] Configuración del render...")
WIDTH = 1280
HEIGHT = 720
MAX_ITER = 150
X_MIN, X_MAX = -2.5, 1.0
Y_MIN, Y_MAX = -1.25, 1.25

print(f"  Resolución: {WIDTH}x{HEIGHT} (720p)")
print(f"  Iteraciones: {MAX_ITER}")
print(f"  Región: [{X_MIN:.2f}, {X_MAX:.2f}] x [{Y_MIN:.2f}, {Y_MAX:.2f}]")

# Renderizar con diferentes backends
results = {}

print("\n" + "=" * 70)
print(" RENDERIZANDO CON DIFERENTES BACKENDS ".center(70, "="))
print("=" * 70)

# Backend 1: Numba
print("\n[Backend 1/2] Numba (CPU Optimizado)")
print("-" * 70)
try:
    renderer = MandelbrotOptimizedRenderer()
    
    print("  Calculando array de iteraciones...")
    start = time.time()
    iterations_numba = renderer.calculate_array(
        WIDTH, HEIGHT, X_MIN, X_MAX, Y_MIN, Y_MAX, MAX_ITER
    )
    calc_time = time.time() - start
    print(f"  ✓ Cálculo completado: {calc_time:.3f}s")
    
    print("  Convirtiendo a RGB...")
    rgb_start = time.time()
    rgb_numba = renderer.render_to_rgb(iterations_numba, MAX_ITER)
    rgb_time = time.time() - rgb_start
    print(f"  ✓ Conversión RGB: {rgb_time:.3f}s")
    
    total_time = calc_time + rgb_time
    print(f"\n  🏁 TIEMPO TOTAL (Numba): {total_time:.3f}s")
    
    results['Numba'] = {
        'time': total_time,
        'calc_time': calc_time,
        'rgb_time': rgb_time,
        'image': Image.fromarray(rgb_numba, mode='RGB'),
        'iterations': iterations_numba
    }
    
except Exception as e:
    print(f"  ✗ Error: {e}")

# Backend 2: CUDA
if CUDA_AVAILABLE:
    print("\n[Backend 2/2] CUDA (GPU)")
    print("-" * 70)
    try:
        renderer = MandelbrotCUDARenderer(device_id=0)
        
        # Obtener info GPU ANTES del render
        mem_before = cp.cuda.Device(0).mem_info
        print(f"  GPU Memoria libre: {mem_before[0] / 1024**3:.2f} GB")
        
        print("  Calculando array en GPU...")
        start = time.time()
        iterations_cuda = renderer.calculate_array(
            WIDTH, HEIGHT, X_MIN, X_MAX, Y_MIN, Y_MAX, MAX_ITER
        )
        calc_time = time.time() - start
        print(f"  ✓ Cálculo GPU completado: {calc_time:.3f}s")
        
        # Info GPU DURANTE el proceso
        mem_during = cp.cuda.Device(0).mem_info
        used = (mem_before[0] - mem_during[0]) / 1024**2
        print(f"  📊 Memoria GPU usada: {used:.1f} MB")
        
        print("  Convirtiendo a RGB (CPU)...")
        rgb_start = time.time()
        rgb_cuda = renderer.render_to_rgb(iterations_cuda, MAX_ITER)
        rgb_time = time.time() - rgb_start
        print(f"  ✓ Conversión RGB: {rgb_time:.3f}s")
        
        total_time = calc_time + rgb_time
        print(f"\n  🏁 TIEMPO TOTAL (CUDA): {total_time:.3f}s")
        
        results['CUDA'] = {
            'time': total_time,
            'calc_time': calc_time,
            'rgb_time': rgb_time,
            'image': Image.fromarray(rgb_cuda, mode='RGB'),
            'iterations': iterations_cuda,
            'gpu_memory_used': used
        }
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()

# Comparar resultados
print("\n" + "=" * 70)
print(" COMPARACIÓN DE RESULTADOS ".center(70, "="))
print("=" * 70)

if 'Numba' in results and 'CUDA' in results:
    print("\n[Validación] Comparando arrays Numba vs CUDA...")
    diff = np.abs(results['Numba']['iterations'] - results['CUDA']['iterations'])
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    
    if max_diff == 0:
        print(f"  ✓ Arrays IDÉNTICOS (diferencia = 0)")
    elif max_diff <= 2:
        print(f"  ✓ Arrays casi idénticos (max diff = {max_diff})")
    else:
        print(f"  ⚠ Diferencias encontradas: max={max_diff}, mean={mean_diff:.4f}")
    
    # Speedup
    speedup = results['Numba']['time'] / results['CUDA']['time']
    print(f"\n[Performance] Speedup CUDA vs Numba: {speedup:.2f}x")
    
    if speedup > 5:
        print("  🚀 CUDA es significativamente más rápido!")
    elif speedup > 2:
        print("  ✓ CUDA es más rápido")
    else:
        print("  ℹ Speedup moderado (transfer overhead en GPU)")

# Crear imagen comparativa
print("\n[PASO 4] Generando visualización comparativa...")

if 'Numba' in results and 'CUDA' in results:
    # Crear figura con 3 subplots: Numba, CUDA, Diferencia
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Numba
    axes[0].imshow(results['Numba']['image'])
    axes[0].set_title(f'Numba (CPU)\n{results["Numba"]["time"]:.3f}s', 
                      fontsize=14, fontweight='bold')
    axes[0].axis('off')
    
    # CUDA
    axes[1].imshow(results['CUDA']['image'])
    axes[1].set_title(f'CUDA (GPU)\n{results["CUDA"]["time"]:.3f}s\nSpeedup: {speedup:.2f}x', 
                      fontsize=14, fontweight='bold', color='green')
    axes[1].axis('off')
    
    # Diferencia
    diff_img = np.abs(results['Numba']['iterations'] - results['CUDA']['iterations'])
    im = axes[2].imshow(diff_img, cmap='hot', vmax=10)
    axes[2].set_title(f'Diferencia Absoluta\nMax: {max_diff}', 
                      fontsize=14, fontweight='bold')
    axes[2].axis('off')
    plt.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04)
    
    plt.suptitle('Comparación: Numba (CPU) vs CUDA (GPU)', 
                 fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    # Guardar
    output_file = 'demo_cuda_comparison.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"  ✓ Guardado: {output_file}")
    plt.close()
    
    # Mostrar imagen
    print(f"\n  📊 Abriendo visualización...")
    img = Image.open(output_file)
    img.show()

elif 'Numba' in results:
    # Solo Numba
    results['Numba']['image'].save('demo_numba_only.png')
    print("  ✓ Guardado: demo_numba_only.png")

# Crear tarjeta de información
if CUDA_AVAILABLE and 'CUDA' in results:
    print("\n[PASO 5] Generando tarjeta de información GPU...")
    
    # Crear imagen con info
    info_img = Image.new('RGB', (800, 600), color='#1a1a1a')
    draw = ImageDraw.Draw(info_img)
    
    # Intentar cargar fuente, si no existe usar default
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
        text_font = ImageFont.truetype("arial.ttf", 20)
        small_font = ImageFont.truetype("arial.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    y = 30
    
    # Título
    draw.text((400, y), "✓ CUDA ACTIVO", fill='#00ff00', 
              font=title_font, anchor='mt')
    y += 60
    
    # Info GPU
    draw.text((50, y), f"GPU: {gpu_info['name']}", fill='white', font=text_font)
    y += 35
    draw.text((50, y), f"Memoria: {gpu_info['memory_total']:.1f} GB", 
              fill='#aaaaaa', font=text_font)
    y += 35
    draw.text((50, y), f"Compute Capability: {gpu_info['compute_capability']}", 
              fill='#aaaaaa', font=text_font)
    y += 60
    
    # Métricas de render
    draw.text((50, y), "MÉTRICAS DE RENDER:", fill='#ffaa00', font=text_font)
    y += 40
    
    draw.text((70, y), f"Resolución: {WIDTH}x{HEIGHT}", fill='white', font=small_font)
    y += 30
    draw.text((70, y), f"Tiempo GPU: {results['CUDA']['calc_time']:.3f}s", 
              fill='#00ff00', font=small_font)
    y += 30
    draw.text((70, y), f"Tiempo total: {results['CUDA']['time']:.3f}s", 
              fill='white', font=small_font)
    y += 30
    draw.text((70, y), f"Memoria GPU usada: {results['CUDA']['gpu_memory_used']:.1f} MB", 
              fill='#00aaff', font=small_font)
    y += 30
    draw.text((70, y), f"Speedup vs CPU: {speedup:.2f}x", 
              fill='#ffff00', font=small_font)
    y += 60
    
    # Status
    draw.text((50, y), "STATUS: Renderizado completado con GPU", 
              fill='#00ff00', font=text_font)
    
    info_img.save('demo_cuda_info.png')
    print("  ✓ Guardado: demo_cuda_info.png")
    info_img.show()

# Resumen final
print("\n" + "=" * 70)
print(" RESUMEN FINAL ".center(70, "="))
print("=" * 70)

if 'CUDA' in results:
    print("\n✓ DEMOSTRACIÓN EXITOSA")
    print(f"\nBackend usado: CUDA GPU")
    print(f"Tiempo: {results['CUDA']['time']:.3f}s")
    print(f"Speedup vs Numba: {speedup:.2f}x")
    print(f"Memoria GPU: {results['CUDA']['gpu_memory_used']:.1f} MB")
    
    print("\nArchivos generados:")
    print("  📊 demo_cuda_comparison.png - Comparación visual")
    print("  📋 demo_cuda_info.png - Información GPU")
    
    print("\n🎉 CUDA está funcionando correctamente en tu sistema!")
    
else:
    print("\n⚠ CUDA no disponible")
    print("  Sistema usará Numba automáticamente")

print("\n" + "=" * 70)
