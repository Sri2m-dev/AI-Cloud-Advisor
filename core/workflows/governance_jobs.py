from datetime import datetime, timezone
from typing import List, Dict, Any

class GovernanceJobs:
    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _parse_utc(value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return GovernanceJobs._utc(parsed)

    @staticmethod
    def find_stale_approvals(approvals: List[Dict[str, Any]], days: int = 7, now: datetime = None) -> List[Dict[str, Any]]:
        now = GovernanceJobs._utc(now or datetime.utcnow())
        return [a for a in approvals if a.get('status') == 'PENDING' and (now - GovernanceJobs._parse_utc(a['created_at'])).days > days]

    @staticmethod
    def find_inactive_saas_users(users: List[Dict[str, Any]], days: int = 30, now: datetime = None) -> List[Dict[str, Any]]:
        now = GovernanceJobs._utc(now or datetime.utcnow())
        return [u for u in users if (now - GovernanceJobs._parse_utc(u['last_active'])).days > days]

    @staticmethod
    def find_orphaned_resources(resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [r for r in resources if r.get('owner') is None or r.get('owner') == '']

    @staticmethod
    def detect_budget_drift(costs: List[Dict[str, Any]], threshold_pct: float = 20.0) -> List[Dict[str, Any]]:
        return [c for c in costs if c.get('budget_drift_pct', 0) > threshold_pct]

    @staticmethod
    def find_unused_commitments(commitments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [c for c in commitments if c.get('usage_pct', 100) < 50]

    @staticmethod
    def scan_anomalies(anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [a for a in anomalies if a.get('severity', '').lower() in {'critical', 'high'}]

