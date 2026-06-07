from typing import Any, Dict
from core.logging.trace_utils import get_timestamp
import services.audit_service as audit_service


class AuditLogger:
    @staticmethod
    def log_event(
        trace_id: str,
        user_id: str,
        action: str,
        resource: str,
        status: str,
        session_id: str = None,
        extra: Dict[str, Any] = None
    ) -> Dict[str, Any]:

        event = {
            "trace_id": trace_id,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "timestamp": get_timestamp(),
            "status": status,
        }

        if session_id:
            event["session_id"] = session_id

        if extra:
            event.update(extra)

        try:
            audit_service.log_event(
                event_type=action.upper(),
                user_id=str(user_id),
                action=action,
                resource_type=resource,
                resource_id=str(resource),
                org_id="1",
                details=event,
                status=status
            )
        except Exception as e:
            print(f"Audit logger error: {e}")

        return event