"""ACT013-DEF-004B durable, authorized governed-workspace resume."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.prospect_data_intake_service import create_prospect_tenant
from universal_evidence.pilot import admit_uploaded_evidence
from universal_evidence.pilot.runtime import reset_configured_runtime_cache
from universal_evidence.production_workflow import (
    persist_production_workspace,
    resumable_production_workspaces,
    resume_production_workspace,
)
from universal_evidence.security import WorkspaceAuthorizationContext

WORKBOOK = Path("tests/fixtures/cmp_p1/fixture_a_cloud_cost.xlsx")
PROFILE = "AWS billing/CUR-derived CSV"


def _authenticated(*, organization_id=None, user_id="ceo-user"):
    organization_id = organization_id or str(uuid4())
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name="Acceptance Tenant",
        user_id=user_id,
        user_email=f"{user_id}@example.com",
        role="executive",
        authorization_claims=frozenset(),
        tenant_id=organization_id,
    )


def _create_workspace(tmp_path, authenticated, *, prospect_name="Acme"):
    key = Fernet.generate_key().decode("ascii")
    # One key is configured per test environment, just as it is in deployment.
    configured = getattr(_create_workspace, "key", None)
    if configured is None:
        _create_workspace.key = key
    key = _create_workspace.key
    tenant = create_prospect_tenant(
        prospect_name,
        consent=True,
        actor=authenticated.user_id,
        role=authenticated.role,
        root=tmp_path / "prospects",
        key=key,
    )
    admission = admit_uploaded_evidence(
        tenant,
        filename=WORKBOOK.name,
        content=WORKBOOK.read_bytes(),
        tenant_context=authenticated,
    )
    authorization = WorkspaceAuthorizationContext.from_authenticated(authenticated)
    persist_production_workspace(
        admission,
        prospect_tenant=tenant,
        prospect_name=prospect_name,
        input_profile=PROFILE,
        authorization=authorization,
    )
    return admission, authorization


@pytest.fixture(autouse=True)
def _configured_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("NEXORA_UNIVERSAL_EVIDENCE_DB", str(tmp_path / "workspace.db"))
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_ROOT", str(tmp_path / "prospects"))
    monkeypatch.setenv("NEXORA_PROSPECT_DATA_KEY", Fernet.generate_key().decode("ascii"))
    if hasattr(_create_workspace, "key"):
        delattr(_create_workspace, "key")
    _create_workspace.key = os.environ["NEXORA_PROSPECT_DATA_KEY"]
    reset_configured_runtime_cache()
    yield
    reset_configured_runtime_cache()


def test_workspace_reconstructs_without_browser_upload_state(tmp_path):
    authenticated = _authenticated()
    original, authorization = _create_workspace(tmp_path, authenticated)

    # Simulate logout/restart by retaining no admission or upload object in memory.
    del original
    reset_configured_runtime_cache()
    locators = resumable_production_workspaces(authorization)
    assert len(locators) == 1
    reconstructed, tenant, prospect_name, profile = resume_production_workspace(
        locators[0], authorization=authorization
    )

    assert reconstructed.fingerprint == locators[0].workspace_id
    assert reconstructed.scope.organization_id == authenticated.organization_id
    assert reconstructed.scope.tenant_id == authenticated.tenant_id
    assert tenant.tenant_id == locators[0].prospect_id
    assert prospect_name == "Acme"
    assert profile == PROFILE


def test_multiple_workspaces_are_bounded_and_never_resolved_as_latest(tmp_path):
    authenticated = _authenticated()
    first, authorization = _create_workspace(tmp_path, authenticated, prospect_name="First")
    second, _ = _create_workspace(tmp_path, authenticated, prospect_name="Second")

    locators = resumable_production_workspaces(authorization)
    assert {item.workspace_id for item in locators} == {first.fingerprint, second.fingerprint}
    assert len(locators) == 2
    resumed = {
        item.workspace_id: resume_production_workspace(item, authorization=authorization)[2]
        for item in locators
    }
    assert resumed == {first.fingerprint: "First", second.fingerprint: "Second"}


def test_workspace_discovery_and_exact_resume_are_tenant_and_owner_isolated(tmp_path):
    authenticated = _authenticated()
    _, authorization = _create_workspace(tmp_path, authenticated)
    locator = resumable_production_workspaces(authorization)[0]

    other_owner = WorkspaceAuthorizationContext.from_authenticated(
        _authenticated(organization_id=authenticated.organization_id, user_id="other-user")
    )
    other_tenant = WorkspaceAuthorizationContext.from_authenticated(_authenticated())
    assert resumable_production_workspaces(other_owner) == ()
    assert resumable_production_workspaces(other_tenant) == ()
    with pytest.raises(PermissionError, match="not authorized"):
        resume_production_workspace(locator, authorization=other_owner)
    with pytest.raises(PermissionError, match="boundary mismatch"):
        resume_production_workspace(locator, authorization=other_tenant)
