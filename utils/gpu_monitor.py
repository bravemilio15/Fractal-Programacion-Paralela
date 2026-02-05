"""
Monitoreo de GPU y CPU en tiempo real.

Utilidades para rastrear uso de GPU (CUDA), memoria, y CPU.
"""

import time
from typing import Dict, Optional

# Intentar importar dependencias
try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class GPUMonitor:
    """Monitor GPU usage in real-time."""
    
    def __init__(self, device_id: int = 0):
        """
        Initialize GPU monitor.
        
        Args:
            device_id: GPU device ID to monitor (default: 0)
        """
        self.device_id = device_id
        self.cuda_available = CUPY_AVAILABLE
        self.device = None
        
        if self.cuda_available:
            try:
                self.device = cp.cuda.Device(device_id)
                # Test access
                _ = self.device.mem_info
            except Exception as e:
                print(f"Warning: CUDA available but device access failed: {e}")
                self.cuda_available = False
    
    def get_gpu_stats(self) -> Dict:
        """
        Get current GPU statistics.
        
        Returns:
            Dictionary with GPU stats or empty if CUDA not available
        """
        if not self.cuda_available or self.device is None:
            return {
                'cuda_available': False,
                'memory_used_mb': 0,
                'memory_total_gb': 0,
                'memory_free_gb': 0,
                'memory_percent': 0
            }
        
        try:
            mem_info = self.device.mem_info
            memory_free = mem_info[0]
            memory_total = mem_info[1]
            memory_used = memory_total - memory_free
            
            return {
                'cuda_available': True,
                'memory_used_mb': memory_used / (1024**2),
                'memory_total_gb': memory_total / (1024**3),
                'memory_free_gb': memory_free / (1024**3),
                'memory_percent': (memory_used / memory_total) * 100 if memory_total > 0 else 0
            }
        except Exception as e:
            print(f"Error getting GPU stats: {e}")
            return {
                'cuda_available': False,
                'memory_used_mb': 0,
                'memory_total_gb': 0,
                'memory_free_gb': 0,
                'memory_percent': 0
            }
    
    def get_cpu_usage(self) -> float:
        """
        Get current CPU usage percentage.
        
        Returns:
            CPU usage % (0-100), or 0 if psutil not available
        """
        if not PSUTIL_AVAILABLE:
            return 0.0
        
        try:
            return psutil.cpu_percent(interval=0.1)
        except:
            return 0.0
    
    def get_combined_stats(self) -> Dict:
        """
        Get both GPU and CPU stats in one call.
        
        Returns:
            Dictionary with all stats
        """
        gpu_stats = self.get_gpu_stats()
        cpu_usage = self.get_cpu_usage()
        
        return {
            **gpu_stats,
            'cpu_percent': cpu_usage,
            'timestamp': time.time()
        }


class PerformanceTracker:
    """Track rendering performance metrics."""
    
    def __init__(self):
        """Initialize performance tracker."""
        self.start_time = None
        self.frames_completed = 0
        self.frame_times = []
        self.current_backend = None
    
    def start(self, backend: str = "Unknown"):
        """
        Start tracking.
        
        Args:
            backend: Name of backend (e.g., "CUDA", "Numba")
        """
        self.start_time = time.time()
        self.frames_completed = 0
        self.frame_times = []
        self.current_backend = backend
    
    def record_frame(self, frame_time: Optional[float] = None):
        """
        Record a completed frame.
        
        Args:
            frame_time: Time to render frame (optional)
        """
        self.frames_completed += 1
        if frame_time is not None:
            self.frame_times.append(frame_time)
    
    def get_fps(self) -> float:
        """
        Get current frames per second.
        
        Returns:
            FPS (frames/second)
        """
        if self.start_time is None or self.frames_completed == 0:
            return 0.0
        
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        
        return self.frames_completed / elapsed
    
    def get_avg_frame_time(self) -> float:
        """
        Get average frame render time.
        
        Returns:
            Average time per frame in seconds
        """
        if not self.frame_times:
            return 0.0
        
        return sum(self.frame_times) / len(self.frame_times)
    
    def get_stats(self) -> Dict:
        """
        Get all performance stats.
        
        Returns:
            Dictionary with performance metrics
        """
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        return {
            'backend': self.current_backend,
            'frames_completed': self.frames_completed,
            'elapsed_time': elapsed,
            'fps': self.get_fps(),
            'avg_frame_time': self.get_avg_frame_time(),
            'total_frames_time': sum(self.frame_times) if self.frame_times else 0
        }


# Singleton instance para uso global
_global_gpu_monitor = None

def get_gpu_monitor() -> GPUMonitor:
    """Get or create global GPU monitor instance."""
    global _global_gpu_monitor
    if _global_gpu_monitor is None:
        _global_gpu_monitor = GPUMonitor()
    return _global_gpu_monitor
