from datetime import datetime, timedelta
from typing import List, Dict, Any

class SLAEscalationEngine:
    @staticmethod
    def check_and_escalate(approvals: List[Dict[str, Any]], now: datetime = None) -> List[Dict[str, Any]]:
        now = now or datetime.utcnow()
        escalated = []
        for approval in approvals:
            created_at = approval.get('created_at')
            if not created_at:
                continue
            created = datetime.fromisoformat(str(created_at).replace('Z', '+00:00'))
            age = (now - created).total_seconds() / 3600
            if age > 48 and approval.get('status') == 'PENDING':
                approval['escalation'] = 'leadership_alert'
                escalated.append(approval)
            elif age > 24 and approval.get('status') == 'PENDING':
                approval['escalation'] = 'escalate'
                escalated.append(approval)
        return escalated

class AutoRoutingEngine:
    @staticmethod
    def route(approval: Dict[str, Any]) -> str:
        if approval.get('cost_risk', 0) > 10000:
            return 'Finance'
        if approval.get('security_risk', '').lower() == 'high':
            return 'Security'
        return 'Default'

