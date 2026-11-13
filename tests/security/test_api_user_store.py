import pytest

from backend.api_user_store import APIUserStoreUnavailable, load_api_users


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "not-json",
        "[]",
        '{"test_operator": "not-a-record"}',
    ],
    ids=["missing", "malformed", "wrong-top-level-type", "wrong-record-type"],
)
def test_invalid_api_user_store_fails_explicitly(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("API_USERS_JSON", raising=False)
    else:
        monkeypatch.setenv("API_USERS_JSON", raw)

    with pytest.raises(APIUserStoreUnavailable):
        load_api_users()


def test_api_user_store_loads_current_authorization_records(monkeypatch):
    monkeypatch.setenv(
        "API_USERS_JSON",
        '{"test_operator": {"role": "Finance", "tenant_id": "tenant-a"}}',
    )

    assert load_api_users() == {
        "test_operator": {
            "role": "Finance",
            "tenant_id": "tenant-a",
        }
    }
