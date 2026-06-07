import pytest
from data_access_layer import approval_repository

def test_fetch_pending_approvals_empty():
    result = approval_repository.fetch_pending_approvals('org1')
    assert isinstance(result, list)
    assert result == []

def test_fetch_approval_by_id_none():
    result = approval_repository.fetch_approval_by_id('approval1')
    assert result is None

def test_update_approval_status():
    assert approval_repository.update_approval_status('approval1', 'APPROVED') is True

def test_insert_audit_event():
    # Should not raise
    approval_repository.insert_audit_event({"event": "test"})

def test_fetch_approval_history_empty():
    result = approval_repository.fetch_approval_history('approval1')
    assert isinstance(result, list)
    assert result == []

