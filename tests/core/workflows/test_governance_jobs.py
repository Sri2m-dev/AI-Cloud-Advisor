from core.workflows.governance_jobs import GovernanceJobs
from datetime import datetime, timedelta

def make_item(created_offset=0, last_active_offset=0, status='PENDING', owner='user', budget_drift_pct=0, usage_pct=100, severity='low'):
    now = datetime.utcnow()
    return {
        'created_at': (now - timedelta(days=created_offset)).isoformat() + 'Z',
        'last_active': (now - timedelta(days=last_active_offset)).isoformat() + 'Z',
        'status': status,
        'owner': owner,
        'budget_drift_pct': budget_drift_pct,
        'usage_pct': usage_pct,
        'severity': severity
    }

def test_find_stale_approvals():
    items = [make_item(created_offset=10), make_item(created_offset=3)]
    result = GovernanceJobs.find_stale_approvals(items, days=7)
    assert len(result) == 1

def test_find_inactive_saas_users():
    users = [make_item(last_active_offset=40), make_item(last_active_offset=10)]
    result = GovernanceJobs.find_inactive_saas_users(users, days=30)
    assert len(result) == 1

def test_find_orphaned_resources():
    resources = [make_item(owner=None), make_item(owner='user')]
    result = GovernanceJobs.find_orphaned_resources(resources)
    assert len(result) == 1

def test_detect_budget_drift():
    costs = [make_item(budget_drift_pct=25), make_item(budget_drift_pct=10)]
    result = GovernanceJobs.detect_budget_drift(costs, threshold_pct=20)
    assert len(result) == 1

def test_find_unused_commitments():
    commitments = [make_item(usage_pct=40), make_item(usage_pct=80)]
    result = GovernanceJobs.find_unused_commitments(commitments)
    assert len(result) == 1

def test_scan_anomalies():
    anomalies = [make_item(severity='critical'), make_item(severity='low')]
    result = GovernanceJobs.scan_anomalies(anomalies)
    assert len(result) == 1

