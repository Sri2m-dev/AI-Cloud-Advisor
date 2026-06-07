import pytest
from validators.user_validator import validate_user_request
from pydantic import ValidationError

def test_valid_user_request():
    payload = {"user_id": "user1", "email": "user1@example.com"}
    result = validate_user_request(payload)
    assert result.user_id == "user1"
    assert result.email == "user1@example.com"

def test_invalid_user_request_missing_email():
    payload = {"user_id": "user1"}
    with pytest.raises(ValidationError):
        validate_user_request(payload)

def test_invalid_user_request_bad_email():
    payload = {"user_id": "user1", "email": "not-an-email"}
    with pytest.raises(ValidationError):
        validate_user_request(payload)

