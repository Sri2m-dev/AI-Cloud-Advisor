import time
from functools import wraps
from core.telemetry.telemetry import Telemetry

def track_latency(event_name: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
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
        return wrapper
    return decorator

