"""Health monitoring for agy-connect sessions."""

from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class HealthStatus:
    """Represents the health of a session."""
    process_alive: bool
    pid: Optional[int]
    uptime: float
    queue_length: int
    memory_usage_mb: Optional[float]
    cpu_usage_percent: Optional[float]
    current_state: str
    last_error: Optional[str]

class HealthMonitor:
    """Tracks and computes health metrics for a session."""
    
    def __init__(self) -> None:
        self._start_time: Optional[float] = None
        self._last_error: Optional[str] = None
        
    def record_start(self) -> None:
        """Record when the process started."""
        self._start_time = time.time()
        self._last_error = None
        
    def record_error(self, error: str) -> None:
        """Record the last encountered error."""
        self._last_error = error
        
    def record_stop(self) -> None:
        """Record when the process stopped."""
        self._start_time = None
        
    def get_uptime(self) -> float:
        """Return the uptime in seconds."""
        if not self._start_time:
            return 0.0
        return time.time() - self._start_time
        
    def get_status(
        self,
        process_alive: bool,
        pid: Optional[int],
        queue_length: int,
        current_state: str,
        memory_mb: Optional[float] = None,
        cpu_percent: Optional[float] = None
    ) -> HealthStatus:
        """Generate a HealthStatus report."""
        return HealthStatus(
            process_alive=process_alive,
            pid=pid,
            uptime=self.get_uptime(),
            queue_length=queue_length,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            current_state=current_state,
            last_error=self._last_error
        )
