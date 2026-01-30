"""
Script de prueba para renderizar un frame de Julia y otro de Mandelbrot.

Este script prueba la integración del conjunto de Julia sin necesidad
de ejecutar el cluster completo.
"""

import io
import sys
from PIL import Image

# Agregar directorio raíz al path
sys.path.insert(0, '.')

from tareas import generar_frame_fractal

def test_julia_frame():
    """Prueba renderizado de un frame de Julia."""
    print("=" * 60)
    print("PRUEBA: Renderizado de Conjunto de Julia")
    print("=" * 60)
    
    params = {
        'frame_num': 0,
        'width': 800,
        'height': 600,
        'max_iter': 100,
        'x_min': -2.0,
        'x_max': 2.0,
        'y_min': -1.5,
        'y_max': 1.5,
        'fractal_type': 'julia',
        'fractal_params': {
            'c_real': -0.7,
            'c_imag': 0.27015
        },
        'use_optimized': True,
        'compress': False
    }
    
    print(f"Renderizando Julia (c = {params['fractal_params']['c_real']}"
          f"{params['fractal_params']['c_imag']:+.4f}i)...")
    
    try:
        frame_num, img_bytes = generar_frame_fractal(params)
        
        # Guardar imagen
        img = Image.open(io.BytesIO(img_bytes))
        output_path = 'test_julia_frame.png'
        img.save(output_path)
        
        print(f"✅ Frame de Julia renderizado exitosamente!")
        print(f"   Tamaño: {len(img_bytes) / 1024:.1f} KB")
        print(f"   Dimensiones: {img.size}")
        print(f"   Guardado en: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error renderizando Julia: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mandelbrot_frame():
    """Prueba renderizado de un frame de Mandelbrot (verificar compatibilidad)."""
    print("\n" + "=" * 60)
    print("PRUEBA: Renderizado de Mandelbrot (compatibilidad)")
    print("=" * 60)
    
    params = {
        'frame_num': 0,
        'width': 800,
        'height': 600,
        'max_iter': 100,
        'x_min': -2.5,
        'x_max': 1.0,
        'y_min': -1.25,
        'y_max': 1.25,
        'fractal_type': 'mandelbrot',
        'use_optimized': True
    }
    
    print("Renderizando Mandelbrot...")
    
    try:
        frame_num, img_bytes = generar_frame_fractal(params)
        
        # Guardar imagen
        img = Image.open(io.BytesIO(img_bytes))
        output_path = 'test_mandelbrot_frame.png'
        img.save(output_path)
        
        print(f"✅ Frame de Mandelbrot renderizado exitosamente!")
        print(f"   Tamaño: {len(img_bytes) / 1024:.1f} KB")
        print(f"   Dimensiones: {img.size}")
        print(f"   Guardado en: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error renderizando Mandelbrot: {e}")
        import traceback
        traceback.print_exc()
        return False


def compare_fractals():
    """Genera comparación lado a lado."""
    print("\n" + "=" * 60)
    print("COMPARACIÓN: Mandelbrot vs Julia")
    print("=" * 60)
    
    try:
        # Cargar imágenes
        img_m = Image.open('test_mandelbrot_frame.png')
        img_j = Image.open('test_julia_frame.png')
        
        # Crear comparación
        width, height = img_m.size
        comparison = Image.new('RGB', (width * 2, height))
        comparison.paste(img_m, (0, 0))
        comparison.paste(img_j, (width, 0))
        
        output_path = 'mandelbrot_vs_julia_comparison.png'
        comparison.save(output_path)
        
        print(f"✅ Comparación generada exitosamente!")
        print(f"   Guardado en: {output_path}")
        print(f"   Mandelbrot (izquierda) | Julia (derecha)")
        return True
        
    except Exception as e:
        print(f"❌ Error generando comparación: {e}")
        return False


if __name__ == "__main__":
    print("\n🧪 INICIANDO PRUEBAS DE INTEGRACIÓN DE JULIA\n")
    
    results = []
    
    # Prueba 1: Julia
    results.append(("Julia", test_julia_frame()))
    
    # Prueba 2: Mandelbrot (compatibilidad)
    results.append(("Mandelbrot", test_mandelbrot_frame()))
    
    # Comparación
    if all(r[1] for r in results):
        results.append(("Comparación", compare_fractals()))
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    if all(r[1] for r in results):
        print("\n🎉 ¡Todas las pruebas pasaron! Julia está integrado correctamente.")
        print("\nPróximos pasos:")
        print("1. Revisar las imágenes generadas:")
        print("   - test_julia_frame.png")
        print("   - test_mandelbrot_frame.png")
        print("   - mandelbrot_vs_julia_comparison.png")
        print("2. Ejecutar renderizado completo con: python master.py --no-gui")
        sys.exit(0)
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisa los errores arriba.")
        sys.exit(1)
