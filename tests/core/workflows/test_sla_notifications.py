from core.workflows.sla_notifications import SLANotificationHandler
import pytest

def test_notify_manager_escalation(capsys):
    approval = {'id': 'A1'}
    SLANotificationHandler.notify_escalation(approval, 'manager_escalation', ['manager@example.com'])
    out = capsys.readouterr().out
    assert '[EMAIL]' in out
    assert '[IN-APP]' in out

def test_notify_leadership_escalation(capsys):
    approval = {'id': 'A2'}
    SLANotificationHandler.notify_escalation(approval, 'leadership_escalation', ['lead@example.com'])
    out = capsys.readouterr().out
    assert '[EMAIL]' in out
    assert '[SLACK]' in out
    assert '[TEAMS]' in out

def test_notify_auto_close(capsys):
    approval = {'id': 'A3'}
    SLANotificationHandler.notify_escalation(approval, 'auto_close_or_escalate', ['admin@example.com'])
    out = capsys.readouterr().out
    assert '[EMAIL]' in out
    assert '[IN-APP]' in out
    assert '[SLACK]' in out
    assert '[TEAMS]' in out

