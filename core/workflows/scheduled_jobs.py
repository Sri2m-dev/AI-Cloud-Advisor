from typing import List, Dict, Any
from datetime import datetime

class GovernanceJobs:
    @staticmethod
    def scan_stale_approvals(approvals: List[Dict[str, Any]], now: datetime = None) -> List[Dict[str, Any]]:
        now = now or datetime.utcnow()
        return [a for a in approvals if a.get('status') == 'PENDING' and (now - datetime.fromisoformat(str(a['created_at']).replace('Z', '+00:00'))).days > 7]

    @staticmethod
    def scan_inactive_saas_users(users: List[Dict[str, Any]], now: datetime = None) -> List[Dict[str, Any]]:
        now = now or datetime.utcnow()
        return [u for u in users if (now - datetime.fromisoformat(str(u['last_active']).replace('Z', '+00:00'))).days > 30]

    @staticmethod
    def scan_anomalies(anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [a for a in anomalies if a.get('severity', '').lower() in {'critical', 'high'}]

    @staticmethod
    def detect_cost_drift(costs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Example: flag if cost increases > 20% over previous period
        flagged = []
        for c in costs:
            if c.get('cost_change_pct', 0) > 20:
                flagged.append(c)
        return flagged

