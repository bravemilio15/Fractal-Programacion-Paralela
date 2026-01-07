"""
Módulo de seguimiento de progreso temporal para recovery de renders.

Este módulo usa JSON para guardar el estado actual del renderizado,
permitiendo recuperación después de crashes o desconexiones.

Diferencia con database.py:
- database.py = Historial permanente (SQLite) 
- progress_tracker.py = Estado temporal (JSON, se borra al completar)
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

from utils.logger import get_master_logger

logger = get_master_logger()


class ProgressTracker:
    """Gestiona el progreso temporal de un render para recovery rápido."""
    
    def __init__(self, render_id: int, save_dir: str = 'cluster_data'):
        """
        Inicializa el tracker de progreso.
        
        Args:
            render_id: ID del render actual
            save_dir: Directorio donde guardar el JSON
        """
        self.render_id = render_id
        self.save_dir = save_dir
        self.progress_file = os.path.join(save_dir, 'current_progress.json')
        
        # Crear directorio si no existe
        os.makedirs(save_dir, exist_ok=True)
        
        # Estado inicial
        self.data = {
            'render_id': render_id,
            'started_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            'completed_frames': [],
            'failed_frames': [],
            'pending_frames': [],
            'workers': {}
        }
        
        logger.debug(f"ProgressTracker iniciado para render #{render_id}")
    
    def save_progress(
        self, 
        completed: Set[int], 
        failed: Set[int], 
        pending: Set[int],
        workers: Optional[Dict[str, Dict]] = None
    ):
        """
        Guarda el progreso actual en JSON.
        
        Args:
            completed: Set de números de frames completados
            failed: Set de números de frames fallidos
            pending: Set de números de frames pendientes
            workers: Diccionario con información de workers activos
        """
        self.data['completed_frames'] = sorted(list(completed))
        self.data['failed_frames'] = sorted(list(failed))
        self.data['pending_frames'] = sorted(list(pending))
        self.data['last_updated'] = datetime.now().isoformat()
        
        if workers:
            self.data['workers'] = workers
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
            
            logger.debug(f"Progreso guardado: {len(completed)} completados, {len(failed)} fallidos, {len(pending)} pendientes")
        except Exception as e:
            logger.error(f"Error guardando progreso: {e}")
    
    def load_progress(self) -> Optional[Dict]:
        """
        Carga el progreso guardado desde el archivo JSON.
        
        Returns:
            Diccionario con el progreso, o None si no existe
        """
        if not os.path.exists(self.progress_file):
            logger.debug("No hay progreso previo para cargar")
            return None
        
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Progreso cargado: render #{data['render_id']}")
            logger.info(f"  - Completados: {len(data['completed_frames'])}")
            logger.info(f"  - Fallidos: {len(data['failed_frames'])}")
            logger.info(f"  - Pendientes: {len(data['pending_frames'])}")
            
            return data
        except Exception as e:
            logger.error(f"Error cargando progreso: {e}")
            return None
    
    def update_worker(self, worker_name: str, current_frame: Optional[int], 
                      completed: int, failed: int, status: str):
        """
        Actualiza información de un worker específico.
        
        Args:
            worker_name: Nombre del worker
            current_frame: Frame que está procesando actualmente (None si idle)
            completed: Total de frames completados por este worker
            failed: Total de frames fallidos por este worker
            status: Estado actual ('connected', 'rendering', 'idle', 'disconnected')
        """
        self.data['workers'][worker_name] = {
            'current_frame': current_frame,
            'completed': completed,
            'failed': failed,
            'status': status,
            'last_seen': datetime.now().isoformat()
        }
        
        # Guardar automáticamente
        self.save_progress(
            set(self.data['completed_frames']),
            set(self.data['failed_frames']),
            set(self.data['pending_frames'])
        )
    
    def remove_worker(self, worker_name: str):
        """Elimina un worker del tracking (cuando se desconecta)."""
        if worker_name in self.data['workers']:
            del self.data['workers'][worker_name]
            logger.debug(f"Worker {worker_name} eliminado del tracker")
    
    def mark_frame_completed(self, frame_num: int):
        """Marca un frame como completado."""
        completed = set(self.data['completed_frames'])
        failed = set(self.data['failed_frames'])
        pending = set(self.data['pending_frames'])
        
        completed.add(frame_num)
        failed.discard(frame_num)
        pending.discard(frame_num)
        
        self.save_progress(completed, failed, pending)
    
    def mark_frame_failed(self, frame_num: int):
        """Marca un frame como fallido."""
        completed = set(self.data['completed_frames'])
        failed = set(self.data['failed_frames'])
        pending = set(self.data['pending_frames'])
        
        failed.add(frame_num)
        completed.discard(frame_num)
        pending.discard(frame_num)
        
        self.save_progress(completed, failed, pending)
    
    def get_completion_percentage(self, total_frames: int) -> float:
        """Calcula el porcentaje de completitud."""
        completed = len(self.data['completed_frames'])
        return (completed / total_frames * 100) if total_frames > 0 else 0
    
    def get_frames_to_retry(self) -> List[int]:
        """Obtiene lista de frames que deben reintentarse (fallidos + pendientes)."""
        return sorted(list(set(self.data['failed_frames'] + self.data['pending_frames'])))
    
    def clear(self):
        """
        Elimina el archivo de progreso.
        Llamar cuando el render se completa exitosamente.
        """
        try:
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
                logger.info(f"Progreso temporal eliminado para render #{self.render_id}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo de progreso: {e}")
    
    @staticmethod
    def has_pending_recovery(save_dir: str = 'cluster_data') -> bool:
        """
        Verifica si existe un progreso pendiente de recuperar.
        
        Args:
            save_dir: Directorio donde buscar el archivo
        
        Returns:
            True si existe un render incompleto
        """
        progress_file = os.path.join(save_dir, 'current_progress.json')
        return os.path.exists(progress_file)
    
    @staticmethod
    def get_recovery_info(save_dir: str = 'cluster_data') -> Optional[Dict]:
        """
        Obtiene información del render pendiente de recuperar.
        
        Returns:
            Diccionario con información básica, o None si no hay nada
        """
        progress_file = os.path.join(save_dir, 'current_progress.json')
        if not os.path.exists(progress_file):
            return None
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            total_processed = len(data['completed_frames']) + len(data['failed_frames'])
            total_pending = len(data['pending_frames'])
            
            return {
                'render_id': data['render_id'],
                'started_at': data['started_at'],
                'completed_count': len(data['completed_frames']),
                'failed_count': len(data['failed_frames']),
                'pending_count': total_pending,
                'workers_last_seen': len(data.get('workers', {}))
            }
        except Exception:
            return None


class RecoveryManager:
    """Gestiona la recuperación de renders después de crashes."""
    
    @staticmethod
    def recover_render(db, tracker: ProgressTracker) -> Dict:
        """
        Recupera un render desde el progreso guardado.
        
        Args:
            db: Instancia de RenderDatabase
            tracker: ProgressTracker con datos cargados
        
        Returns:
            Diccionario con información de recuperación
        """
        # Acceder a los datos del tracker
        progress = tracker.data
        render_id = progress['render_id']
        
        # Obtener info del render desde la DB
        render_info = db.get_render(render_id)
        if not render_info:
            logger.error(f"Render #{render_id} no encontrado en base de datos")
            return {}
        
        # Calcular qué frames faltan
        completed_frames = set(progress['completed_frames'])
        failed_frames = set(progress['failed_frames'])
        pending_frames = set(progress['pending_frames'])
        
        total_frames = render_info['total_frames']
        all_frames = set(range(total_frames))
        
        # Frames que necesitan renderearse = pendientes + fallidos
        frames_to_render = sorted(list(pending_frames | failed_frames))
        
        recovery_info = {
            'render_id': render_id,
            'total_frames': total_frames,
            'completed': len(completed_frames),
            'frames_to_render': frames_to_render,
            'estimated_time_saved': len(completed_frames) * 2.0,  # Estimación: 2s por frame
            'can_resume': len(completed_frames) > 0
        }
        
        logger.info(f"Recovery preparado: {len(completed_frames)}/{total_frames} frames ya completados")
        logger.info(f"  → Quedan {len(frames_to_render)} frames por renderizar")
        
        return recovery_info
