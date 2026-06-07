import pytest
from core.workflows.sla_engine import SLAEngine
from datetime import datetime, timedelta

def make_approval(hours_ago, status='PENDING'):
    created_at = (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat() + 'Z'
    return {'created_at': created_at, 'status': status}

def test_no_breach():
    approval = make_approval(10)
    assert SLAEngine.detect_breach(approval) == 'ok'

def test_manager_escalation():
    approval = make_approval(25)
    assert SLAEngine.detect_breach(approval) == 'manager_escalation'

def test_leadership_escalation():
    approval = make_approval(49)
    assert SLAEngine.detect_breach(approval) == 'leadership_escalation'

def test_auto_close():
    approval = make_approval(73)
    assert SLAEngine.detect_breach(approval) == 'auto_close_or_escalate'

def test_response_metrics():
    approvals = [make_approval(10), make_approval(25), make_approval(49), make_approval(73)]
    metrics = SLAEngine.response_metrics(approvals)
    assert metrics['total'] == 4
    assert metrics['breached'] == 3
    assert metrics['avg_age_hours'] > 0

