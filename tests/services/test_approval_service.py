import pytest

from core.permissions.decorators import PermissionDenied
from services import approval_service


def test_approve_request_rbac():
    with pytest.raises(PermissionDenied):
        approval_service.approve_request("approval1", "user1", user_role="Analyst")


def test_approve_request_role_check_is_not_committed_success():
    from auth.authenticated_tenant import ProtectedWorkflowUnavailable
    with pytest.raises(ProtectedWorkflowUnavailable):
        approval_service.approve_request("approval1", "user1", user_role="Admin")


def test_reject_request_rbac():
    with pytest.raises(PermissionDenied):
        approval_service.reject_request("approval1", "user1", user_role="Analyst")


def test_reject_request_role_check_is_not_committed_success():
    from auth.authenticated_tenant import ProtectedWorkflowUnavailable
    with pytest.raises(ProtectedWorkflowUnavailable):
        approval_service.reject_request("approval1", "user1", user_role="Manager")


def test_dashboard_reads_degrade_safely_when_supabase_is_unconfigured(monkeypatch):
    def unavailable():
        raise RuntimeError("SUPABASE_URL is required to initialize the Supabase client")

    monkeypatch.setattr(
        "repositories.approval_repository.ApprovalRepository.get_all_approvals",
        unavailable,
    )
    assert approval_service.ApprovalService.get_all_approvals() == []
    assert approval_service.ApprovalService.get_dashboard_metrics() == {
        "pending": 0,
        "approved": 0,
        "rejected": 0,
        "escalated": 0,
        "total": 0,
    }
