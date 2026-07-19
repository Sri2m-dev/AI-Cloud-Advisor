from __future__ import annotations

import pytest

from auth.tenant_authorization import TenantAuthorizationContext, TenantAuthorizationError
from auth.tenant_boundaries import (
    authorize_ai,
    authorize_api,
    authorize_cache,
    authorize_connector,
    authorize_event,
    authorize_job,
    authorize_streamlit,
)


def _context(subject_type="service", boundary="background_job", permissions=()):
    return TenantAuthorizationContext(
        organization_id="org-a",
        tenant_id="tenant-a",
        subject_id="subject-1",
        subject_type=subject_type,
        permissions=frozenset(permissions),
        source_boundary=boundary,
    )


@pytest.mark.parametrize("missing", ["organization_id", "tenant_id", "subject_id"])
def test_missing_identity_context_is_denied(missing):
    values = dict(
        organization_id="org-a",
        tenant_id="tenant-a",
        subject_id="subject-1",
        subject_type="user",
        source_boundary="api",
    )
    values[missing] = ""
    with pytest.raises(TenantAuthorizationError):
        TenantAuthorizationContext(**values)


def test_api_denies_cross_tenant_and_missing_permission():
    principal = {
        "organization_id": "org-a",
        "tenant_id": "tenant-a",
        "sub": "user-1",
        "permissions": ["cost:read"],
    }
    with pytest.raises(TenantAuthorizationError, match="tenant boundary mismatch"):
        authorize_api(principal, "tenant-b", "cost:read")
    with pytest.raises(TenantAuthorizationError, match="permission denied"):
        authorize_api(principal, "tenant-a", "cost:write")


def test_single_permission_string_is_not_split_into_characters():
    context = TenantAuthorizationContext.from_principal(
        {
            "tenant_id": "tenant-a",
            "sub": "user-1",
            "permissions": "cost:read",
        },
        source_boundary="api",
    )

    assert context.permissions == frozenset({"cost:read"})


def test_streamlit_denies_requested_organization_mismatch():
    principal = {
        "organization_id": "org-a",
        "tenant_id": "tenant-a",
        "username": "user-1",
        "permissions": ["page:read"],
    }
    with pytest.raises(TenantAuthorizationError, match="organization boundary mismatch"):
        authorize_streamlit(principal, "org-b", "page:read")


def test_connector_cannot_use_fallback_or_other_organization():
    context = _context(permissions={"connector:run"})
    with pytest.raises(TenantAuthorizationError):
        authorize_connector(context, "")
    with pytest.raises(TenantAuthorizationError, match="organization boundary mismatch"):
        authorize_connector(context, "org-b")


def test_cache_key_is_always_tenant_partitioned():
    context = _context(permissions={"cache:access"})
    assert authorize_cache(context, "ai-context", "asset-1") == (
        "ai-context",
        "org-a",
        "tenant-a",
        "asset-1",
    )
    with pytest.raises(TenantAuthorizationError):
        authorize_cache(context, "ai-context", "")


def test_background_job_requires_trusted_matching_scope():
    context = _context(permissions={"job:execute"})
    authorize_job(context, {"organization_id": "org-a", "tenant_id": "tenant-a"})
    with pytest.raises(TenantAuthorizationError, match="tenant boundary mismatch"):
        authorize_job(context, {"organization_id": "org-a", "tenant_id": "tenant-b"})
    with pytest.raises(TenantAuthorizationError, match="trusted service"):
        authorize_job(
            _context(subject_type="user", permissions={"job:execute"}),
            {"organization_id": "org-a", "tenant_id": "tenant-a"},
        )


def test_event_consumer_denies_cross_tenant_payload():
    context = _context(
        subject_type="event_consumer",
        boundary="event_consumer",
        permissions={"event:consume"},
    )
    with pytest.raises(TenantAuthorizationError, match="organization boundary mismatch"):
        authorize_event(context, {"organization_id": "org-b", "tenant_id": "tenant-a"})


def test_ai_service_denies_cross_tenant_and_untrusted_context():
    context = _context(
        subject_type="ai_service", boundary="ai_service", permissions={"ai:read"}
    )
    with pytest.raises(TenantAuthorizationError, match="organization boundary mismatch"):
        authorize_ai(context, "org-b")
    with pytest.raises(TenantAuthorizationError, match="untrusted ai_service context"):
        authorize_ai(
            _context(subject_type="ai_service", boundary="api", permissions={"ai:read"}),
            "org-a",
        )
