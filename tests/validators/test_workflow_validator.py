import pytest
from validators.workflow_validator import WorkflowRequest
from pydantic import ValidationError

def test_valid_workflow_request():
    payload = {"workflow_id": "wf1", "steps": ["a", "b"], "owner_id": "user1"}
    result = WorkflowRequest.validate_workflow_request(payload)
    assert result.workflow_id == "wf1"
    assert result.owner_id == "user1"

def test_invalid_workflow_request_missing_steps():
    payload = {"workflow_id": "wf1", "owner_id": "user1"}
    with pytest.raises(ValidationError):
        WorkflowRequest.validate_workflow_request(payload)

