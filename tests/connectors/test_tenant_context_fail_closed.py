import pytest

from connectors.common.tenant_guard import (
    ensure_payload_organization,
    require_organization_id,
    resolve_organization_id,
    with_organization,
)


def test_missing_organization_context_fails_closed():
    with pytest.raises(ValueError, match="implicit tenant fallback is disabled"):
        resolve_organization_id()
    with pytest.raises(ValueError, match="implicit tenant fallback is disabled"):
        require_organization_id()


def test_payload_helpers_require_explicit_context():
    with pytest.raises(ValueError, match="implicit tenant fallback is disabled"):
        ensure_payload_organization({"resource_id": "resource-1"})
    with pytest.raises(ValueError, match="implicit tenant fallback is disabled"):
        with_organization([{"resource_id": "resource-1"}], "")


def test_explicit_context_is_preserved():
    assert resolve_organization_id("org-1") == "org-1"
    assert ensure_payload_organization({"resource_id": "resource-1"}, "org-1") == {
        "resource_id": "resource-1",
        "organization_id": "org-1",
    }
