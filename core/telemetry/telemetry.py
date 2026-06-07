import time
from typing import Callable, Any, Dict, Optional
import logging

logger = logging.getLogger("telemetry")

class Telemetry:
    @staticmethod
    def track_event(event_name: str, properties: Optional[Dict[str, Any]] = None):
        logger.info(f"[TELEMETRY] {event_name} | {properties or {}}")

    @staticmethod
    def track_latency(event_name: str, func: Callable, *args, **kwargs) -> Any:
        start = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start
            Telemetry.track_event(f"{event_name}_latency", {"duration": duration})
            return result
        except Exception as e:
            duration = time.time() - start
            Telemetry.track_event(f"{event_name}_failure", {"duration": duration, "error": str(e)})
            raise

    @staticmethod
    def track_failure(event_name: str, details: Optional[Dict[str, Any]] = None):
        Telemetry.track_event(f"{event_name}_failure", details)

