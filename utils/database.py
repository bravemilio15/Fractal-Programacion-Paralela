"""
Módulo de base de datos para gestionar historial de renders del cluster.

Este módulo proporciona una interfaz para SQLite que almacena:
- Historial de renders (sesiones de renderizado)
- Frames individuales con su estado
- Información de workers conectados
- Estadísticas de rendimiento

Soporta múltiples tipos de fractales (Mandelbrot, Julia, etc.)
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from utils.logger import get_master_logger

logger = get_master_logger()


class RenderDatabase:
    """Gestiona la base de datos de historial de renders."""
    
    def __init__(self, db_path: str = 'cluster_data/renders.db'):
        """
        Inicializa la conexión a la base de datos.
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
        self.db_path = db_path
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Inicializar base de datos
        self.init_database()
        
        logger.info(f"Base de datos inicializada en: {db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permite acceso por nombre de columna
        return conn
    
    def init_database(self):
        """Crea el schema de la base de datos si no existe."""
        schema_path = Path(__file__).parent.parent / 'cluster_data' / 'schema.sql'
        
        if not schema_path.exists():
            logger.warning(f"Schema SQL no encontrado en {schema_path}")
            return
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        conn = self._get_connection()
        try:
            conn.executescript(schema_sql)
            conn.commit()
            logger.info("Schema de base de datos creado exitosamente")
        except Exception as e:
            logger.error(f"Error creando schema: {e}")
            raise
        finally:
            conn.close()
    
    # ========================================
    # GESTIÓN DE TIPOS DE FRACTALES
    # ========================================
    
    def add_fractal_type(self, name: str, description: str, renderer_class: str) -> int:
        """
        Agrega un nuevo tipo de fractal al catálogo.
        
        Args:
            name: Nombre único del fractal
            description: Descripción
            renderer_class: Nombre de la clase Python del renderer
        
        Returns:
            ID del tipo de fractal creado
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO fractal_types (name, description, renderer_class) VALUES (?, ?, ?)",
                (name, description, renderer_class)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Tipo de fractal '{name}' ya existe")
            cursor = conn.execute("SELECT id FROM fractal_types WHERE name = ?", (name,))
            return cursor.fetchone()[0]
        finally:
            conn.close()
    
    def get_fractal_type_id(self, name: str) -> Optional[int]:
        """Obtiene el ID de un tipo de fractal por nombre."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT id FROM fractal_types WHERE name = ?", (name,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    
    # ========================================
    # GESTIÓN DE RENDERS
    # ========================================
    
    def start_render(self, fractal_type: str, config: Dict[str, Any]) -> int:
        """
        Inicia un nuevo render y registra su configuración.
        
        Args:
            fractal_type: Nombre del tipo de fractal ('mandelbrot', 'julia', etc.)
            config: Diccionario con configuración del render
        
        Returns:
            ID del render creado
        """
        fractal_type_id = self.get_fractal_type_id(fractal_type)
        if not fractal_type_id:
            raise ValueError(f"Tipo de fractal '{fractal_type}' no existe")
        
        # Extraer configuración específica del fractal
        fractal_config = {
            'zoom_inicial': config.get('zoom_inicial', 1.0),
            'zoom_final': config.get('zoom_final', 1000),
            'x_centro': config.get('x_centro', 0),
            'y_centro': config.get('y_centro', 0),
        }
        
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO renders (
                    fractal_type_id, preset, width, height, total_frames, max_iter,
                    fractal_config, status, started_at, output_dir
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?)
            """, (
                fractal_type_id,
                config.get('preset', 'custom'),
                config['width'],
                config['height'],
                config['total_frames'],
                config['max_iter'],
                json.dumps(fractal_config),
                datetime.now().isoformat(),
                config.get('output_dir', './frames_renderizados')
            ))
            conn.commit()
            render_id = cursor.lastrowid
            
            logger.info(f"Render #{render_id} iniciado: {config['total_frames']} frames de {fractal_type}")
            return render_id
        finally:
            conn.close()
    
    def update_render_status(self, render_id: int, status: str):
        """Actualiza el estado de un render."""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE renders SET status = ? WHERE id = ?",
                (status, render_id)
            )
            conn.commit()
            logger.debug(f"Render #{render_id} → estado: {status}")
        finally:
            conn.close()
    
    def complete_render(self, render_id: int, total_time: float, video_path: Optional[str] = None):
        """
        Marca un render como completado.
        
        Args:
            render_id: ID del render
            total_time: Tiempo total en segundos
            video_path: Ruta al video generado (opcional)
        """
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE renders 
                SET status = 'completed', 
                    completed_at = ?, 
                    total_time = ?,
                    video_path = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), total_time, video_path, render_id))
            conn.commit()
            
            logger.info(f"Render #{render_id} completado en {total_time:.2f}s")
        finally:
            conn.close()
    
    def get_render(self, render_id: int) -> Optional[Dict]:
        """Obtiene información completa de un render."""
        conn = self._get_connection()
        try:
            # Usar tabla directa para incluir fractal_config
            cursor = conn.execute("""
                SELECT r.*, ft.name as fractal_type
                FROM renders r
                LEFT JOIN fractal_types ft ON r.fractal_type_id = ft.id
                WHERE r.id = ?
            """, (render_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def list_renders(self, limit: int = 50, status: Optional[str] = None) -> List[Dict]:
        """
        Lista renders recientes.
        
        Args:
            limit: Número máximo de resultados
            status: Filtrar por estado (opcional)
        
        Returns:
            Lista de renders ordenados por fecha descendente
        """
        conn = self._get_connection()
        try:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM v_renders_full WHERE status = ? ORDER BY timestamp DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM v_renders_full ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    # ========================================
    # GESTIÓN DE FRAMES
    # ========================================
    
    def add_frame(self, render_id: int, frame_num: int, status: str = 'pending') -> int:
        """Agrega un frame a la cola de renderizado."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO frames (render_id, frame_num, status) VALUES (?, ?, ?)",
                (render_id, frame_num, status)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Frame ya existe
            cursor = conn.execute(
                "SELECT id FROM frames WHERE render_id = ? AND frame_num = ?",
                (render_id, frame_num)
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()
    
    def update_frame(
        self, 
        render_id: int, 
        frame_num: int, 
        status: str, 
        worker_name: Optional[str] = None,
        render_time: Optional[float] = None,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """Actualiza el estado y metadata de un frame."""
        conn = self._get_connection()
        try:
            updates = {"status": status}
            
            if worker_name:
                updates["worker_name"] = worker_name
            
            if status == 'rendering':
                updates["started_at"] = datetime.now().isoformat()
            elif status == 'completed':
                updates["completed_at"] = datetime.now().isoformat()
                if render_time:
                    updates["render_time"] = render_time
                if file_path:
                    updates["file_path"] = file_path
                if file_size:
                    updates["file_size"] = file_size
            elif status == 'failed':
                updates["error_message"] = error_message
                # Incrementar retries
                conn.execute(
                    "UPDATE frames SET retries = retries + 1 WHERE render_id = ? AND frame_num = ?",
                    (render_id, frame_num)
                )
            
            # Construir query de actualización
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [render_id, frame_num]
            
            conn.execute(
                f"UPDATE frames SET {set_clause} WHERE render_id = ? AND frame_num = ?",
                values
            )
            conn.commit()
        finally:
            conn.close()
    
    def get_pending_frames(self, render_id: int) -> List[int]:
        """Obtiene lista de frames pendientes."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT frame_num FROM frames WHERE render_id = ? AND status IN ('pending', 'failed') ORDER BY frame_num",
                (render_id,)
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_failed_frames(self, render_id: int) -> List[Dict]:
        """Obtiene frames fallidos con información de error."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT frame_num, error_message, retries FROM frames WHERE render_id = ? AND status = 'failed'",
                (render_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    # ========================================
    # GESTIÓN DE WORKERS
    # ========================================
    
    def add_worker(self, render_id: int, worker_name: str, ip_address: str) -> int:
        """Registra la conexión de un worker."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                INSERT INTO workers (render_id, worker_name, ip_address, connected_at, status)
                VALUES (?, ?, ?, ?, 'connected')
            """, (render_id, worker_name, ip_address, datetime.now().isoformat()))
            conn.commit()
            
            logger.info(f"Worker '{worker_name}' conectado al render #{render_id}")
            return cursor.lastrowid
        finally:
            conn.close()
    
    def disconnect_worker(self, render_id: int, worker_name: str):
        """Marca un worker como desconectado."""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE workers 
                SET status = 'disconnected', disconnected_at = ?
                WHERE render_id = ? AND worker_name = ? AND status = 'connected'
            """, (datetime.now().isoformat(), render_id, worker_name))
            conn.commit()
            
            logger.warning(f"Worker '{worker_name}' desconectado del render #{render_id}")
        finally:
            conn.close()
    
    def get_worker_stats(self, render_id: int) -> List[Dict]:
        """Obtiene estadísticas de workers para un render."""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM v_worker_stats WHERE render_id = ?",
                (render_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    # ========================================
    # ESTADÍSTICAS
    # ========================================
    
    def get_render_stats(self, render_id: int) -> Dict:
        """Obtiene estadísticas completas de un render."""
        conn = self._get_connection()
        try:
            # Info básica
            render = self.get_render(render_id)
            if not render:
                return {}
            
            # Estadísticas de frames
            cursor = conn.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    AVG(render_time) as avg_time
                FROM frames
                WHERE render_id = ?
                GROUP BY status
            """, (render_id,))
            
            frame_stats = {row['status']: {
                'count': row['count'],
                'avg_time': row['avg_time']
            } for row in cursor.fetchall()}
            
            # Estadísticas de workers
            worker_stats = self.get_worker_stats(render_id)
            
            return {
                'render': render,
                'frames': frame_stats,
                'workers': worker_stats
            }
        finally:
            conn.close()
