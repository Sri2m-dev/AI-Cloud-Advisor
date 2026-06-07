from datetime import datetime, timezone
from typing import List, Dict, Any

class SLAEngine:
    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def get_aging_hours(created_at: str, now: datetime = None) -> float:
        now = SLAEngine._utc(now or datetime.utcnow())
        created = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
        created = SLAEngine._utc(created)
        return (now - created).total_seconds() / 3600

    @staticmethod
    def detect_breach(approval: Dict[str, Any], now: datetime = None) -> str:
        hours = SLAEngine.get_aging_hours(approval.get('created_at'), now)
        if hours > 72 and approval.get('status') == 'PENDING':
            return 'auto_close_or_escalate'
        if hours > 48 and approval.get('status') == 'PENDING':
            return 'leadership_escalation'
        if hours > 24 and approval.get('status') == 'PENDING':
            return 'manager_escalation'
        return 'ok'

    @staticmethod
    def process_approvals(approvals: List[Dict[str, Any]], now: datetime = None) -> List[Dict[str, Any]]:
        now = SLAEngine._utc(now or datetime.utcnow())
        results = []
        for approval in approvals:
            breach = SLAEngine.detect_breach(approval, now)
            approval['sla_status'] = breach
            results.append(approval)
        return results

    @staticmethod
    def response_metrics(approvals: List[Dict[str, Any]], now: datetime = None) -> Dict[str, Any]:
        now = SLAEngine._utc(now or datetime.utcnow())
        total = len(approvals)
        breached = sum(1 for a in approvals if SLAEngine.detect_breach(a, now) != 'ok')
        avg_age = sum(SLAEngine.get_aging_hours(a.get('created_at'), now) for a in approvals) / total if total else 0
        return {
            'total': total,
            'breached': breached,
            'avg_age_hours': avg_age
        }

