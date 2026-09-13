"""Security and functionality acceptance suite for Customer Onboarding & Administration."""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from auth.authenticated_tenant import AuthenticatedTenantContext
from services import local_auth_service, onboarding_service
from services.onboarding_service import (
    AuthorizationError,
    OnboardingError,
    OnboardingState,
    accept_invitation,
    create_invitation,
    create_organization_and_onboard,
    get_invitation_by_token,
    get_user_onboarding_state,
    is_clean_workspace,
    revoke_invitation,
)


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_onboarding.db"

    def get_test_conn():
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(onboarding_service, "get_db", get_test_conn)
    monkeypatch.setattr(local_auth_service, "get_db", get_test_conn)
    return get_test_conn


def test_invalid_email_or_name_rejected(test_db):
    with pytest.raises(OnboardingError, match="valid email"):
        create_organization_and_onboard("invalid-email", "Acme Corp")

    with pytest.raises(OnboardingError, match="Organization name cannot be empty"):
        create_organization_and_onboard("admin@acme.com", "   ")

    with pytest.raises(OnboardingError, match="between 2 and 100"):
        create_organization_and_onboard("admin@acme.com", "A")


def test_valid_organization_creation_succeeds_with_admin_membership(test_db):
    result = create_organization_and_onboard(
        user_email="admin@acme.com",
        organization_name="Acme Corporation",
        admin_role="client_admin",
        password="securePassword123!",
    )

    assert result.success is True
    assert result.state == OnboardingState.ONBOARDING_COMPLETE
    assert result.organization is not None
    assert result.organization.organization_name == "Acme Corporation"
    # Ensure canonical UUID was generated
    org_uuid = uuid.UUID(result.organization.organization_id)
    assert str(org_uuid) == result.organization.organization_id
    assert result.role == "client_admin"

    # Verify user state
    state, org_info = get_user_onboarding_state("admin@acme.com")
    assert state == OnboardingState.ONBOARDING_COMPLETE
    assert org_info.organization_id == result.organization.organization_id
    assert org_info.organization_name == "Acme Corporation"


def test_session_tenant_context_binds_to_new_organization(test_db):
    result = create_organization_and_onboard(
        user_email="founder@startup.io",
        organization_name="Startup IO",
        admin_role="client_admin",
    )

    org_id = result.organization.organization_id
    session_payload = {
        "authenticated": True,
        "auth_backend": "local",
        "organization_id": org_id,
        "org_id": org_id,
        "tenant_id": org_id,
        "authorized_organization_ids": [org_id],
        "organization_name": "Startup IO",
        "email": "founder@startup.io",
        "role": "client_admin",
    }

    context = AuthenticatedTenantContext.from_session(
        session_payload,
        organization_resolver=lambda oid: "Startup IO" if oid == org_id else None,
    )

    assert context.organization_id == org_id
    assert context.tenant_id == org_id
    assert context.organization_name == "Startup IO"
    assert context.user_email == "founder@startup.io"
    assert context.role == "client_admin"


def test_clean_workspace_initialization(test_db):
    result = create_organization_and_onboard(
        user_email="clean@enterprise.com",
        organization_name="Clean Enterprise",
    )
    org_id = result.organization.organization_id

    # Verify newly created organization has 0 leaked records
    assert is_clean_workspace(org_id) is True


def test_unauthorized_user_cannot_issue_invitation(test_db):
    # Setup organization with admin
    res = create_organization_and_onboard("admin@org1.com", "Org One")
    org1_id = res.organization.organization_id

    # Create non-admin user in Org One
    conn = test_db()
    conn.execute(
        """
        INSERT INTO local_auth_users (
            email, password_hash, role, organization_id, organization_name, created_at
        ) VALUES ('viewer@org1.com', 'hash', 'viewer', ?, 'Org One', '2026-09-13T00:00:00')
        """,
        (org1_id,),
    )
    conn.commit()
    conn.close()

    # Viewer cannot invite
    with pytest.raises(AuthorizationError, match="Only organization administrators"):
        create_invitation(
            inviter_email="viewer@org1.com",
            organization_id=org1_id,
            invitee_email="newbie@org1.com",
            role="finance",
        )

    # User from another org cannot invite into Org One
    create_organization_and_onboard("admin@org2.com", "Org Two")
    with pytest.raises(AuthorizationError, match="not an active member"):
        create_invitation(
            inviter_email="admin@org2.com",
            organization_id=org1_id,
            invitee_email="newbie@org1.com",
            role="finance",
        )


def test_invitation_lifecycle_invite_and_accept(test_db):
    res = create_organization_and_onboard("admin@corp.com", "Corp Inc")
    org_id = res.organization.organization_id

    # Issue invitation
    invitation = create_invitation(
        inviter_email="admin@corp.com",
        organization_id=org_id,
        invitee_email="cfo@corp.com",
        role="finance",
        expiry_days=7,
    )

    assert invitation.state == "INVITED"
    assert invitation.email == "cfo@corp.com"
    assert invitation.role == "finance"
    assert invitation.token is not None

    # Retrieve invitation by token
    retrieved = get_invitation_by_token(invitation.token)
    assert retrieved is not None
    assert retrieved.invitation_id == invitation.invitation_id

    # Accept invitation
    accept_res = accept_invitation(
        token=invitation.token,
        user_email="cfo@corp.com",
        password="cfoPassword123!",
    )

    assert accept_res.success is True
    assert accept_res.organization.organization_id == org_id
    assert accept_res.role == "finance"

    # Verify user is now an active member
    state, org_info = get_user_onboarding_state("cfo@corp.com")
    assert state == OnboardingState.ONBOARDING_COMPLETE
    assert org_info.organization_id == org_id

    # Verify invitation marked accepted
    updated_inv = get_invitation_by_token(invitation.token)
    assert updated_inv.state == "ACCEPTED"

    # Cannot re-accept already accepted invitation
    with pytest.raises(OnboardingError, match="cannot be accepted in 'ACCEPTED' state"):
        accept_invitation(invitation.token, "cfo@corp.com")


def test_cross_tenant_invitation_acceptance_protection(test_db):
    res1 = create_organization_and_onboard("admin@tenant1.com", "Tenant One")
    org1_id = res1.organization.organization_id

    create_organization_and_onboard("admin@tenant2.com", "Tenant Two")

    inv = create_invitation(
        inviter_email="admin@tenant1.com",
        organization_id=org1_id,
        invitee_email="worker@tenant1.com",
        role="operations",
    )

    # Different email cannot claim the invitation
    with pytest.raises(AuthorizationError, match="Invitation was issued for"):
        accept_invitation(inv.token, "impostor@tenant2.com")


def test_duplicate_active_invitation_prevention(test_db):
    res = create_organization_and_onboard("admin@org.com", "Organization Alpha")
    org_id = res.organization.organization_id

    create_invitation(
        inviter_email="admin@org.com",
        organization_id=org_id,
        invitee_email="user@org.com",
        role="executive",
    )

    # Second active invitation to same email must fail
    with pytest.raises(OnboardingError, match="active invitation already exists"):
        create_invitation(
            inviter_email="admin@org.com",
            organization_id=org_id,
            invitee_email="user@org.com",
            role="executive",
        )


def test_expired_invitation_rejected(test_db):
    res = create_organization_and_onboard("admin@expired.com", "Expired Org")
    org_id = res.organization.organization_id

    # Create an already expired invitation directly in DB
    conn = test_db()
    past_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO organization_invitations (
            invitation_id, organization_id, organization_name, email, role,
            invited_by_email, token, state, created_at, expires_at
        ) VALUES ('inv-exp-1', ?, 'Expired Org', 'late@expired.com', 'finance',
                  'admin@expired.com', 'tok-expired', 'INVITED', ?, ?)
        """,
        (org_id, past_iso, past_iso),
    )
    conn.commit()
    conn.close()

    inv = get_invitation_by_token("tok-expired")
    assert inv.state == "EXPIRED"

    with pytest.raises(OnboardingError, match="cannot be accepted in 'EXPIRED' state"):
        accept_invitation("tok-expired", "late@expired.com")


def test_revocation_lifecycle_and_cross_tenant_protection(test_db):
    res1 = create_organization_and_onboard("admin@org1.com", "Org One")
    org1_id = res1.organization.organization_id

    res2 = create_organization_and_onboard("admin@org2.com", "Org Two")
    org2_id = res2.organization.organization_id

    inv = create_invitation(
        inviter_email="admin@org1.com",
        organization_id=org1_id,
        invitee_email="cancelme@org1.com",
        role="executive",
    )

    # Admin from Org Two cannot revoke Org One's invitation
    with pytest.raises(AuthorizationError, match="Cannot revoke invitation"):
        revoke_invitation(
            invitation_id=inv.invitation_id,
            revoker_email="admin@org2.com",
            organization_id=org2_id,
        )

    # Org One Admin successfully revokes
    assert revoke_invitation(
        invitation_id=inv.invitation_id,
        revoker_email="admin@org1.com",
        organization_id=org1_id,
    ) is True

    # Revoked invitation cannot be accepted
    with pytest.raises(OnboardingError, match="cannot be accepted in 'REVOKED' state"):
        accept_invitation(inv.token, "cancelme@org1.com")


def test_production_mode_does_not_invoke_demo_persona_seeding(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AUTH_MODE", raising=False)

    changed = local_auth_service.ensure_nonproduction_personas(environment="production")
    assert changed == 0


def test_already_existing_member_cannot_be_invited(test_db):
    res = create_organization_and_onboard("admin@company.com", "Company LLC")
    org_id = res.organization.organization_id

    # Add member
    conn = test_db()
    conn.execute(
        """
        INSERT INTO local_auth_users (
            email, password_hash, role, organization_id, organization_name, created_at
        ) VALUES ('dev@company.com', 'pwdhash', 'technical', ?, 'Company LLC', '2026-09-13T00:00')
        """,
        (org_id,),
    )
    conn.commit()
    conn.close()

    # Attempting to invite existing member must fail
    with pytest.raises(OnboardingError, match="already a member"):
        create_invitation(
            inviter_email="admin@company.com",
            organization_id=org_id,
            invitee_email="dev@company.com",
            role="technical",
        )


def test_user_onboarding_state_progression(test_db):
    # Non-existent user
    state, org = get_user_onboarding_state("unknown@domain.com")
    assert state == OnboardingState.ACCOUNT_AUTHENTICATED
    assert org is None

    # User with empty organization_id
    conn = test_db()
    conn.execute(
        """
        INSERT INTO local_auth_users (
            email, password_hash, role, organization_id, organization_name, created_at
        ) VALUES ('pending@domain.com', 'pwd', 'viewer', '', '', '2026-09-13T00:00:00')
        """,
    )
    conn.commit()
    conn.close()

    state, org = get_user_onboarding_state("pending@domain.com")
    assert state == OnboardingState.ORGANIZATION_REQUIRED
    assert org is None

    # Create org for user
    res = create_organization_and_onboard("pending@domain.com", "New Enterprise")
    state, org = get_user_onboarding_state("pending@domain.com")
    assert state == OnboardingState.ONBOARDING_COMPLETE
    assert org.organization_id == res.organization.organization_id

