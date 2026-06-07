import pytest
from services.recommendation_service import _latest_workflow_state

def test_latest_workflow_state_fallback():
    rec_id = 123
    fallback = 'PENDING_APPROVAL'
    result = _latest_workflow_state(rec_id, fallback)
    assert result == 'PENDING_APPROVAL'

