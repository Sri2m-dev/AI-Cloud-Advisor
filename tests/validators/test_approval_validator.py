import pytest
from validators.approval_validator import validate_approval_request
from pydantic import ValidationError

def test_valid_approval_request():
    payload = {"org_id": "org1", "user_id": "user1", "amount": 100.0}
    result = validate_approval_request(payload)
    assert result.org_id == "org1"
    assert result.user_id == "user1"

def test_invalid_approval_request_missing_org():
    payload = {"user_id": "user1", "amount": 100.0}
    with pytest.raises(ValidationError):
        validate_approval_request(payload)

def test_invalid_approval_request_empty_user():
    payload = {"org_id": "org1", "user_id": "", "amount": 100.0}
    with pytest.raises(ValidationError):
        validate_approval_request(payload)

