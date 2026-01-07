"""Estimador de tiempo de renderizado."""

import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from .logger import setup_logger

logger = setup_logger('estimator')


class RenderEstimator:
    """Estima tiempos de renderizado basándose en historial."""
    
    def __init__(self, history_file: str = "./config/render_history.json"):
        """
        Inicializa el estimador.
        
        Args:
            history_file: Archivo donde guardar historial de renderizados
        """
        self.history_file = Path(history_file)
        self.history: List[Dict[str, Any]] = []
        self.load_history()
    
    def load_history(self) -> None:
        """Carga el historial desde archivo."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
                logger.info(f"Historial cargado: {len(self.history)} registros")
            except Exception as e:
                logger.warning(f"Error cargando historial: {e}")
                self.history = []
    
    def save_history(self) -> None:
        """Guarda el historial en archivo."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando historial: {e}")
    
    def record(
        self,
        width: int,
        height: int,
        max_iter: int,
        num_frames: int,
        num_workers: int,
        time_seconds: float,
        optimized: bool = False
    ) -> None:
        """
        Registra un renderizado completado.
        
        Args:
            width: Ancho en píxeles
            height: Alto en píxeles
            max_iter: Iteraciones máximas
            num_frames: Número de frames
            num_workers: Workers utilizados
            time_seconds: Tiempo total en segundos
            optimized: Si se usó versión optimizada
        """
        record = {
            'width': width,
            'height': height,
            'max_iter': max_iter,
            'num_frames': num_frames,
            'num_workers': num_workers,
            'time_seconds': time_seconds,
            'optimized': optimized,
            'pixels': width * height,
            'time_per_frame': time_seconds / num_frames if num_frames > 0 else 0
        }
        
        self.history.append(record)
        
        # Mantener solo últimos 100 registros
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        self.save_history()
        logger.info(f"Renderizado registrado: {time_seconds:.1f}s para {num_frames} frames")
    
    def estimate(
        self,
        width: int,
        height: int,
        max_iter: int,
        num_frames: int,
        num_workers: int,
        optimized: bool = False
    ) -> Optional[float]:
        """
        Estima el tiempo de renderizado.
        
        Args:
            width: Ancho en píxeles
            height: Alto en píxeles
            max_iter: Iteraciones máximas
            num_frames: Número de frames
            num_workers: Workers disponibles
            optimized: Si se usará versión optimizada
        
        Returns:
            Tiempo estimado en segundos o None si no hay datos
        """
        if not self.history:
            # Estimación heurística si no hay historial
            return self._heuristic_estimate(width, height, max_iter, num_frames, num_workers, optimized)
        
        # Buscar renderizados similares
        pixels = width * height
        similar = [
            h for h in self.history
            if (
                abs(h['pixels'] - pixels) < pixels * 0.3 and  # ±30% píxeles
                abs(h['max_iter'] - max_iter) < max_iter * 0.3 and  # ±30% iteraciones
                h['optimized'] == optimized  # Mismo modo
            )
        ]
        
        if similar:
            # Promedio de tiempos similares
            avg_time_per_frame = sum(h['time_per_frame'] for h in similar) / len(similar)
            
            # Ajustar por número de workers
            avg_workers = sum(h['num_workers'] for h in similar) / len(similar)
            worker_factor = avg_workers / max(num_workers, 1)
            
            estimated = avg_time_per_frame * num_frames * worker_factor
            
            logger.info(f"Estimación basada en {len(similar)} renderizados similares: {estimated:.1f}s")
            return estimated
        
        # Si no hay similares, usar heurística
        return self._heuristic_estimate(width, height, max_iter, num_frames, num_workers, optimized)
    
    def _heuristic_estimate(
        self,
        width: int,
        height: int,
        max_iter: int,
        num_frames: int,
        num_workers: int,
        optimized: bool
    ) -> float:
        """
        Estimación heurística sin historial.
        
        Returns:
            Tiempo estimado en segundos
        """
        pixels = width * height
        complexity = max_iter
        
        # Tiempo base por millón de píxeles-iteraciones
        if optimized:
            # Versión optimizada es ~50x más rápida
            base_time_per_million = 0.02  # segundos
        else:
            base_time_per_million = 1.0  # segundos
        
        total_work = (pixels * complexity * num_frames) / 1_000_000
        base_time = total_work * base_time_per_million
        
        # Ajustar por paralelización (no es lineal)
        if num_workers > 1:
            # Eficiencia de paralelización ~80%
            parallel_efficiency = 0.8
            speedup = 1 + (num_workers - 1) * parallel_efficiency
            estimated = base_time / speedup
        else:
            estimated = base_time
        
        logger.info(f"Estimación heurística: {estimated:.1f}s")
        return estimated
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del historial.
        
        Returns:
            Diccionario con estadísticas
        """
        if not self.history:
            return {'num_records': 0}
        
        total_time = sum(h['time_seconds'] for h in self.history)
        total_frames = sum(h['num_frames'] for h in self.history)
        
        return {
            'num_records': len(self.history),
            'total_time_hours': total_time / 3600,
            'total_frames': total_frames,
            'avg_time_per_frame': total_time / total_frames if total_frames > 0 else 0,
            'optimized_count': sum(1 for h in self.history if h['optimized'])
        }
