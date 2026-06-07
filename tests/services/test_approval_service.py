import pytest
from services import approval_service
from core.permissions.decorators import PermissionDenied

def test_approve_request_rbac():
    with pytest.raises(PermissionDenied):
        approval_service.approve_request('approval1', 'user1', user_role='Analyst')

def test_approve_request_success():
    resp = approval_service.approve_request('approval1', 'user1', user_role='Admin')
    assert resp.success
    assert 'trace_id' in resp.data
    assert 'request_id' in resp.data

def test_reject_request_rbac():
    with pytest.raises(PermissionDenied):
        approval_service.reject_request('approval1', 'user1', user_role='Analyst')

def test_reject_request_success():
    resp = approval_service.reject_request('approval1', 'user1', user_role='Manager')
    assert resp.success
    assert 'trace_id' in resp.data
    assert 'request_id' in resp.data

