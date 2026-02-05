"""
Configuración GPU INTENSIVA para maximizar uso de GPU.

Este script crea un render de alta intensidad diseñado para:
- Saturar los 5120 CUDA cores de la RTX 5070 Ti
- Minimizar uso de CPU
- Demostrar máximo rendimiento GPU
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fractals import MandelbrotCUDARenderer
import numpy as np
import time
from PIL import Image

print("="*70)
print("CONFIGURACIÓN GPU INTENSIVA - RTX 5070 Ti")
print("="*70)

# Verificar GPU
try:
    import cupy as cp
    print(f"\n✓ CuPy disponible")
    device = cp.cuda.Device(0)
    props = cp.cuda.runtime.getDeviceProperties(0)
    print(f"✓ GPU: {props['name'].decode()}")
    print(f"✓ CUDA Cores: ~5120")
    print(f"✓ Memoria: {props['totalGlobalMem'] / (1024**3):.1f} GB")
except:
    print("\n✗ CUDA no disponible")
    sys.exit(1)

# CONFIGURACIÓN GPU INTENSIVA
print("\n" + "="*70)
print("CONFIGURACIÓN PARA SATURAR GPU")
print("="*70)

configs = [
    {
        'name': 'Warm-up (720p)',
        'width': 1280,
        'height': 720,
        'iterations': 500,
        'description': 'Calentamiento GPU'
    },
    {
        'name': 'Medium Intensity (1080p)',
        'width': 1920,
        'height': 1080,
        'iterations': 1000,
        'description': 'Intensidad media - ~2M píxeles'
    },
    {
        'name': 'High Intensity (4K)',
        'width': 3840,
        'height': 2160,
        'iterations': 2000,
        'description': 'Alta intensidad - ~8.3M píxeles'
    },
    {
        'name': 'EXTREME (8K)',
        'width': 7680,
        'height': 4320,
        'iterations': 3000,
        'description': '⚠️ EXTREMO - ~33M píxeles - SATURACIÓN COMPLETA'
    }
]

print("\nOpciones disponibles:")
for i, cfg in enumerate(configs):
    print(f"{i+1}. {cfg['name']}")
    print(f"   {cfg['width']}x{cfg['height']} @ {cfg['iterations']} iter")
    print(f"   {cfg['description']}")
    print()

choice = input("Seleccionar configuración (1-4) [default=3]: ").strip() or "3"
config_idx = int(choice) - 1

if config_idx < 0 or config_idx >= len(configs):
    print("Opción inválida, usando configuración 3 (4K)")
    config_idx = 2

selected = configs[config_idx]

print("\n" + "="*70)
print(f"CONFIGURACIÓN SELECCIONADA: {selected['name']}")
print("="*70)
print(f"Resolución: {selected['width']}x{selected['height']}")
print(f"Iteraciones: {selected['iterations']}")
print(f"Total píxeles: {selected['width'] * selected['height']:,}")
print(f"Operaciones: ~{selected['width'] * selected['height'] * selected['iterations'] / 1e9:.2f} Billion ops")
print()

# Configuración de región
x_min, x_max = -2.5, 1.0
y_min, y_max = -1.25, 1.25

# Crear renderer CUDA
print("Inicializando CUDA renderer...")
renderer = MandelbrotCUDARenderer(
    width=selected['width'],
    height=selected['height'],
    max_iter=selected['iterations']
)

print(f"✓ Renderer creado")
print(f"✓ Memoria GPU requerida: ~{(selected['width'] * selected['height'] * 4) / (1024**2):.1f} MB")
print()

# ========================
# RENDER GPU INTENSIVO
# ========================

print("="*70)
print("INICIANDO RENDER GPU INTENSIVO")
print("="*70)
print("Monitoreando uso de GPU...")
print()

# Warm-up
print("[Warm-up] Compilando kernel CUDA...")
_ = renderer.calculate_array(x_min, x_max, y_min, y_max)
print("✓ Kernel compilado (JIT completado)")
print()

# Render principal
print(f"[RENDER] Procesando {selected['width']}x{selected['height']} @ {selected['iterations']} iter...")
print("Observa el panel de métricas - GPU debería subir significativamente")
print()

# Medir tiempo
start = time.time()

# CÁLCULO EN GPU (puro)
iterations_array = renderer.calculate_array(x_min, x_max, y_min, y_max)

gpu_time = time.time() - start

# Obtener uso de memoria GPU
mem_info = device.mem_info
mem_used = (mem_info[1] - mem_info[0]) / (1024**2)

print(f"\n✓ Cálculo GPU completado: {gpu_time:.3f}s")
print(f"✓ GPU Memory usada: {mem_used:.1f} MB")
print(f"✓ Throughput: {(selected['width'] * selected['height']) / gpu_time / 1e6:.2f} MPixels/s")
print(f"✓ GFLOPS estimado: {(selected['width'] * selected['height'] * selected['iterations']) / gpu_time / 1e9:.2f}")
print()

# Conversión a RGB (en CPU - mínima)
print("[POST] Convirtiendo a RGB (CPU)...")
start_rgb = time.time()
rgb_array = renderer.to_rgb(iterations_array)
rgb_time = time.time() - start_rgb

print(f"✓ Conversión RGB: {rgb_time:.3f}s")
print(f"✓ Tiempo total: {gpu_time + rgb_time:.3f}s")
print(f"✓ % GPU: {(gpu_time / (gpu_time + rgb_time)) * 100:.1f}%")
print()

# Guardar resultado
output_file = f"gpu_intensive_{selected['width']}x{selected['height']}.png"
print(f"[SAVE] Guardando: {output_file}")
img = Image.fromarray(rgb_array, 'RGB')
img.save(output_file, optimize=True)

print(f"✓ Guardado: {output_file}")
print()

# ========================
# RESUMEN
# ========================

print("="*70)
print("RESUMEN DE RENDIMIENTO")
print("="*70)
print(f"GPU: {props['name'].decode()}")
print(f"Resolución: {selected['width']}x{selected['height']} ({selected['width'] * selected['height']:,} píxeles)")
print(f"Iteraciones: {selected['iterations']:,}")
print(f"")
print(f"Tiempo GPU (cálculo): {gpu_time:.3f}s")
print(f"Tiempo CPU (RGB):     {rgb_time:.3f}s")
print(f"Tiempo Total:         {gpu_time + rgb_time:.3f}s")
print(f"")
print(f"Memoria GPU usada:    {mem_used:.1f} MB")
print(f"Throughput:           {(selected['width'] * selected['height']) / gpu_time / 1e6:.2f} MPixels/s")
print(f"GFLOPS estimado:      {(selected['width'] * selected['height'] * selected['iterations']) / gpu_time / 1e9:.2f}")
print()

print("="*70)
print("VERIFICAR EN PANEL DE MÉTRICAS:")
print("="*70)
print("Durante el cálculo GPU deberías haber visto:")
print("  • GPU Usage: 80-100% (saturación)")
print("  • GPU Memory: Subida significativa")
print("  • CPU Usage: Relativamente bajo")
print("="*70)
