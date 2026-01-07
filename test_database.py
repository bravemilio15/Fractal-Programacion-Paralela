"""
Script de pruebas para verificar el sistema de persistencia del cluster.

Ejecuta cada función paso a paso para probar todas las funcionalidades.
"""

import os
import sys
from utils.database import RenderDatabase
from utils.progress_tracker import ProgressTracker

def test_1_database_creation():
    """PRUEBA 1: Verificar que la base de datos se crea correctamente."""
    print("\n" + "="*60)
    print("PRUEBA 1: Creación de Base de Datos")
    print("="*60)
    
    db = RenderDatabase()
    db_path = 'cluster_data/renders.db'
    
    if os.path.exists(db_path):
        print("✅ Base de datos creada en:", os.path.abspath(db_path))
        print(f"   Tamaño: {os.path.getsize(db_path)} bytes")
    else:
        print("❌ ERROR: Base de datos no existe")
        return False
    
    return True


def test_2_view_database_content():
    """PRUEBA 2: Ver qué hay guardado en la base de datos actualmente."""
    print("\n" + "="*60)
    print("PRUEBA 2: Contenido Actual de la Base de Datos")
    print("="*60)
    
    db = RenderDatabase()
    
    # Ver todos los renders
    renders = db.list_renders(limit=100)
    
    print(f"\n📊 Total de renders guardados: {len(renders)}")
    print("-" * 60)
    
    if len(renders) == 0:
        print("ℹ️  No hay renders guardados aún.")
        print("   Ejecuta un render para ver datos aquí.")
        return True
    
    for render in renders:
        print(f"\n🎬 Render #{render['id']} - {render['fractal_type']}")
        print(f"   📅 Fecha: {render['timestamp']}")
        print(f"   📐 Resolución: {render['width']}x{render['height']}")
        print(f"   🎞️  Frames: {render['frames_completed']}/{render['total_frames']}")
        print(f"   ⏱️  Tiempo: {render['total_time']:.2f}s" if render['total_time'] else "   ⏱️  Tiempo: En progreso")
        print(f"   ✅ Estado: {render['status']}")
        print(f"   👥 Workers: {render['total_workers']}")
        
        if render['video_path']:
            print(f"   🎬 Video: {render['video_path']}")
    
    return True


def test_3_view_detailed_stats(render_id=None):
    """PRUEBA 3: Ver estadísticas detalladas de un render específico."""
    print("\n" + "="*60)
    print("PRUEBA 3: Estadísticas Detalladas")
    print("="*60)
    
    db = RenderDatabase()
    
    # Si no se especifica render_id, usar el más reciente
    if render_id is None:
        renders = db.list_renders(limit=1)
        if len(renders) == 0:
            print("ℹ️  No hay renders para mostrar estadísticas.")
            return True
        render_id = renders[0]['id']
    
    print(f"\n📊 Estadísticas del Render #{render_id}")
    print("-" * 60)
    
    stats = db.get_render_stats(render_id)
    
    if not stats:
        print(f"❌ ERROR: Render #{render_id} no encontrado")
        return False
    
    # Información general
    print(f"\n🎬 Información General:")
    print(f"   Preset: {stats['render']['preset']}")
    print(f"   Resolución: {stats['render']['width']}x{stats['render']['height']}")
    print(f"   Frames totales: {stats['render']['total_frames']}")
    print(f"   Iteraciones: {stats['render']['max_iter']}")
    
    # Estadísticas de frames
    print(f"\n📊 Frames por Estado:")
    for status, info in stats['frames'].items():
        avg_time = info['avg_time'] if info['avg_time'] else 0
        print(f"   {status:12s}: {info['count']:3d} frames (promedio {avg_time:.2f}s)")
    
    # Estadísticas de workers
    print(f"\n👥 Workers que participaron:")
    if len(stats['workers']) == 0:
        print("   (Ninguno aún)")
    else:
        for worker in stats['workers']:
            print(f"\n   Worker: {worker['worker_name']}")
            print(f"      IP: {worker['ip_address']}")
            print(f"      Conectado: {worker['connected_at']}")
            print(f"      Frames completados: {worker['frames_completed']}")
            if worker['avg_frame_time']:
                print(f"      Tiempo promedio: {worker['avg_frame_time']:.2f}s/frame")
            if worker['success_rate']:
                print(f"      Tasa de éxito: {worker['success_rate']:.1f}%")
    
    return True


def test_4_view_frame_details(render_id=None):
    """PRUEBA 4: Ver detalles de frames individuales."""
    print("\n" + "="*60)
    print("PRUEBA 4: Detalles de Frames Individuales")
    print("="*60)
    
    db = RenderDatabase()
    
    if render_id is None:
        renders = db.list_renders(limit=1)
        if len(renders) == 0:
            print("ℹ️  No hay renders para mostrar frames.")
            return True
        render_id = renders[0]['id']
    
    # Obtener frames completados
    conn = db._get_connection()
    cursor = conn.execute("""
        SELECT frame_num, worker_name, render_time, file_size, status
        FROM frames
        WHERE render_id = ?
        ORDER BY frame_num
        LIMIT 10
    """, (render_id,))
    
    frames = cursor.fetchall()
    conn.close()
    
    print(f"\n📋 Primeros 10 frames del Render #{render_id}:")
    print("-" * 60)
    
    if len(frames) == 0:
        print("   (No hay frames registrados)")
        return True
    
    for frame in frames:
        frame_dict = dict(frame)
        print(f"\n   Frame #{frame_dict['frame_num']:04d}")
        print(f"      Worker: {frame_dict['worker_name'] or 'No asignado'}")
        print(f"      Estado: {frame_dict['status']}")
        if frame_dict['render_time']:
            print(f"      Tiempo: {frame_dict['render_time']:.2f}s")
        if frame_dict['file_size']:
            print(f"      Tamaño: {frame_dict['file_size']/1024:.1f} KB")
    
    return True


def test_5_check_recovery():
    """PRUEBA 5: Verificar si hay progreso pendiente de recuperar."""
    print("\n" + "="*60)
    print("PRUEBA 5: Sistema de Recovery")
    print("="*60)
    
    if ProgressTracker.has_pending_recovery():
        print("\n⚠️  ¡HAY UN RENDER INCOMPLETO!")
        recovery_info = ProgressTracker.get_recovery_info()
        
        print(f"   Render ID: {recovery_info['render_id']}")
        print(f"   Iniciado: {recovery_info['started_at']}")
        print(f"   Completados: {recovery_info['completed_count']} frames")
        print(f"   Fallidos: {recovery_info['failed_count']} frames")
        print(f"   Pendientes: {recovery_info['pending_count']} frames")
        print(f"\n   Al iniciar el master, se te preguntará si quieres recuperarlo.")
    else:
        print("\n✅ No hay renders pendientes de recuperar.")
        print("   (Para probar recovery, cancela un render a mitad de camino)")
    
    return True


def test_6_query_examples():
    """PRUEBA 6: Ejemplos de queries útiles."""
    print("\n" + "="*60)
    print("PRUEBA 6: Queries Útiles")
    print("="*60)
    
    db = RenderDatabase()
    conn = db._get_connection()
    
    # Query 1: Total de frames renderizados
    cursor = conn.execute("SELECT COUNT(*) as total FROM frames WHERE status = 'completed'")
    total_frames = cursor.fetchone()[0]
    print(f"\n📊 Total de frames completados: {total_frames}")
    
    # Query 2: Tiempo total de renderizado
    cursor = conn.execute("SELECT SUM(total_time) as total FROM renders WHERE status = 'completed'")
    total_time = cursor.fetchone()[0] or 0
    print(f"⏱️  Tiempo total de renderizado: {total_time:.2f}s ({total_time/60:.1f} min)")
    
    # Query 3: Worker más productivo
    cursor = conn.execute("""
        SELECT worker_name, COUNT(*) as frames
        FROM frames 
        WHERE status = 'completed' AND worker_name IS NOT NULL
        GROUP BY worker_name
        ORDER BY frames DESC
        LIMIT 1
    """)
    top_worker = cursor.fetchone()
    if top_worker:
        print(f"🏆 Worker más productivo: {top_worker[0]} ({top_worker[1]} frames)")
    
    # Query 4: Promedio de tiempo por frame
    cursor = conn.execute("SELECT AVG(render_time) as avg FROM frames WHERE status = 'completed'")
    avg_time = cursor.fetchone()[0]
    if avg_time:
        print(f"📈 Tiempo promedio por frame: {avg_time:.2f}s")
    
    conn.close()
    return True


def run_all_tests():
    """Ejecuta todas las pruebas."""
    print("\n" + "🧪" * 30)
    print(" SUITE DE PRUEBAS DEL SISTEMA DE PERSISTENCIA")
    print("🧪" * 30)
    
    tests = [
        test_1_database_creation,
        test_2_view_database_content,
        test_3_view_detailed_stats,
        test_4_view_frame_details,
        test_5_check_recovery,
        test_6_query_examples,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ ERROR en {test.__name__}: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESUMEN: {passed} pruebas pasadas, {failed} fallidas")
    print("="*60)


if __name__ == '__main__':
    print("\n🔍 Sistema de Pruebas del Cluster de Renderizado")
    print("Puedes ejecutar pruebas individuales o todas juntas.\n")
    
    print("Opciones:")
    print("  1. Ver contenido de la base de datos")
    print("  2. Ver estadísticas detalladas")
    print("  3. Ver detalles de frames")
    print("  4. Verificar recovery")
    print("  5. Queries útiles")
    print("  6. Ejecutar todas las pruebas")
    
    try:
        opcion = input("\nSelecciona opción (1-6): ").strip()
        
        if opcion == '1':
            test_2_view_database_content()
        elif opcion == '2':
            test_3_view_detailed_stats()
        elif opcion == '3':
            test_4_view_frame_details()
        elif opcion == '4':
            test_5_check_recovery()
        elif opcion == '5':
            test_6_query_examples()
        elif opcion == '6':
            run_all_tests()
        else:
            print("Opción inválida. Ejecutando todas las pruebas...")
            run_all_tests()
    except KeyboardInterrupt:
        print("\n\nPruebas canceladas.")
