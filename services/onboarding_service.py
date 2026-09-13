"""Enterprise Customer Onboarding & Administration Service.

Provides governed organization provisioning, tenant initialization, and
invitation management for Nexora enterprise customers.
"""

from __future__ import annotations

import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from auth.role_constants import ROLES, normalize_role
from database.db import get_db
from services import audit_service


class OnboardingState(str, Enum):
    ACCOUNT_AUTHENTICATED = "ACCOUNT_AUTHENTICATED"
    ORGANIZATION_REQUIRED = "ORGANIZATION_REQUIRED"
    ORGANIZATION_CREATED = "ORGANIZATION_CREATED"
    ADMIN_MEMBERSHIP_CREATED = "ADMIN_MEMBERSHIP_CREATED"
    WORKSPACE_INITIALIZED = "WORKSPACE_INITIALIZED"
    ONBOARDING_COMPLETE = "ONBOARDING_COMPLETE"


class InvitationState(str, Enum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class OnboardingError(ValueError):
    """Raised when onboarding validation fails."""


class AuthorizationError(PermissionError):
    """Raised when an onboarding or invitation action lacks authority."""


@dataclass(frozen=True)
class OrganizationInfo:
    organization_id: str
    organization_name: str
    created_at: str
    status: str
    created_by: str


@dataclass(frozen=True)
class InvitationInfo:
    invitation_id: str
    organization_id: str
    organization_name: str
    email: str
    role: str
    invited_by_email: str
    token: str
    state: str
    created_at: str
    expires_at: str
    accepted_at: str | None = None
    revoked_at: str | None = None


@dataclass(frozen=True)
class OnboardingResult:
    success: bool
    state: OnboardingState
    organization: OrganizationInfo | None = None
    user_email: str | None = None
    role: str | None = None
    error: str | None = None


_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(email: str) -> str:
    normalized = str(email or "").strip().lower()
    if not normalized or not _EMAIL_REGEX.match(normalized):
        raise OnboardingError("A valid email address is required")
    return normalized


def _validate_org_name(name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise OnboardingError("Organization name cannot be empty")
    if len(normalized) < 2 or len(normalized) > 100:
        raise OnboardingError("Organization name must be between 2 and 100 characters")
    if any(ord(c) < 32 for c in normalized):
        raise OnboardingError("Organization name contains invalid control characters")
    return normalized


def _ensure_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_by TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS organization_invitations (
            invitation_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            organization_name TEXT NOT NULL,
            email TEXT NOT NULL COLLATE NOCASE,
            role TEXT NOT NULL,
            invited_by_email TEXT NOT NULL COLLATE NOCASE,
            token TEXT NOT NULL UNIQUE,
            state TEXT NOT NULL DEFAULT 'INVITED',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            accepted_at TEXT,
            revoked_at TEXT
        )
        """
    )
    # Ensure local_auth_users schema exists
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS local_auth_users (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            organization_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def get_user_onboarding_state(
    email: str,
    *,
    conn=None,
) -> tuple[OnboardingState, OrganizationInfo | None]:
    """Inspect user and return current onboarding state and organization."""
    normalized_email = _normalize_email(email)
    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        _ensure_tables(conn)
        user_row = conn.execute(
            """
            SELECT email, role, organization_id, organization_name
            FROM local_auth_users WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()

        if not user_row:
            return OnboardingState.ACCOUNT_AUTHENTICATED, None

        org_id = str(user_row["organization_id"] or "").strip()
        if not org_id or org_id == "00000000-0000-0000-0000-000000000000":
            return OnboardingState.ORGANIZATION_REQUIRED, None

        org_row = conn.execute(
            "SELECT id, name, created_at, status, created_by FROM organizations WHERE id = ?",
            (org_id,),
        ).fetchone()

        if not org_row:
            # Fallback info from user record if organization table row not yet created
            org_info = OrganizationInfo(
                organization_id=org_id,
                organization_name=user_row["organization_name"],
                created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                status="active",
                created_by=normalized_email,
            )
        else:
            org_info = OrganizationInfo(
                organization_id=org_row["id"],
                organization_name=org_row["name"],
                created_at=org_row["created_at"],
                status=org_row["status"],
                created_by=org_row["created_by"] or normalized_email,
            )

        return OnboardingState.ONBOARDING_COMPLETE, org_info
    finally:
        if owns_connection:
            conn.close()


def create_organization_and_onboard(
    user_email: str,
    organization_name: str,
    *,
    admin_role: str = "client_admin",
    password: str | None = None,
    conn=None,
) -> OnboardingResult:
    """Create a new tenant organization and provision the creator as tenant admin."""
    normalized_email = _normalize_email(user_email)
    valid_name = _validate_org_name(organization_name)
    canonical_role = normalize_role(admin_role)
    if canonical_role not in {"client_admin", "super_admin", "admin"}:
        canonical_role = "client_admin"

    new_org_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        _ensure_tables(conn)

        # Check existing user
        user_row = conn.execute(
            """
            SELECT email, password_hash, role, organization_id
            FROM local_auth_users WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()

        # Insert organization record
        conn.execute(
            """
            INSERT INTO organizations (id, name, created_at, status, created_by)
            VALUES (?, ?, ?, 'active', ?)
            """,
            (new_org_id, valid_name, now, normalized_email),
        )

        from services.local_auth_service import _password_hash

        if user_row:
            # User already authenticated; update organization binding and admin role
            pwd_hash = user_row["password_hash"]
            if password:
                pwd_hash = _password_hash(password)
            conn.execute(
                """
                UPDATE local_auth_users
                SET role = ?, organization_id = ?, organization_name = ?, password_hash = ?
                WHERE email = ?
                """,
                (canonical_role, new_org_id, valid_name, pwd_hash, normalized_email),
            )
        else:
            if not password:
                # Default temporary password if not provided
                password = secrets.token_urlsafe(16)
            conn.execute(
                """
                INSERT INTO local_auth_users (
                    email, password_hash, role, organization_id, organization_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_email,
                    _password_hash(password),
                    canonical_role,
                    new_org_id,
                    valid_name,
                    now,
                ),
            )

        if owns_connection:
            conn.commit()

        # Audit logging
        try:
            audit_service.log_event(
                event_type="ORGANIZATION_CREATED",
                user_id=normalized_email,
                action="organization_created",
                resource_type="organization",
                resource_id=new_org_id,
                org_id=new_org_id,
                details={
                    "organization_name": valid_name,
                    "creator_role": canonical_role,
                    "state": OnboardingState.ONBOARDING_COMPLETE.value,
                },
                status="success",
            )
        except Exception:
            pass

        org_info = OrganizationInfo(
            organization_id=new_org_id,
            organization_name=valid_name,
            created_at=now,
            status="active",
            created_by=normalized_email,
        )

        return OnboardingResult(
            success=True,
            state=OnboardingState.ONBOARDING_COMPLETE,
            organization=org_info,
            user_email=normalized_email,
            role=canonical_role,
        )
    except Exception as exc:
        if owns_connection:
            try:
                conn.rollback()
            except Exception:
                pass
        return OnboardingResult(
            success=False,
            state=OnboardingState.ORGANIZATION_REQUIRED,
            error=str(exc),
        )
    finally:
        if owns_connection:
            conn.close()


def create_invitation(
    inviter_email: str,
    organization_id: str,
    invitee_email: str,
    role: str,
    *,
    expiry_days: int = 7,
    conn=None,
) -> InvitationInfo:
    """Issue a tenant-scoped invitation to join an organization."""
    normalized_inviter = _normalize_email(inviter_email)
    normalized_invitee = _normalize_email(invitee_email)
    canonical_role = normalize_role(role)
    if canonical_role not in ROLES:
        raise OnboardingError(f"Invalid role: {role}")

    org_id = str(uuid.UUID(str(organization_id).strip()))

    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        _ensure_tables(conn)

        # 1. Verify inviter authority in this organization
        inviter_row = conn.execute(
            "SELECT role, organization_id, organization_name FROM local_auth_users WHERE email = ?",
            (normalized_inviter,),
        ).fetchone()

        if not inviter_row or str(inviter_row["organization_id"]) != org_id:
            raise AuthorizationError("Inviter is not an active member of this organization")

        inviter_role = normalize_role(inviter_row["role"])
        if inviter_role not in {"super_admin", "client_admin", "admin"}:
            raise AuthorizationError("Only organization administrators can invite users")

        org_name = str(inviter_row["organization_name"])

        # 2. Check if invitee is already a member of this organization
        existing_member = conn.execute(
            "SELECT 1 FROM local_auth_users WHERE email = ? AND organization_id = ?",
            (normalized_invitee, org_id),
        ).fetchone()
        if existing_member:
            raise OnboardingError(f"{normalized_invitee} is already a member of this organization")

        # 3. Check for existing active invitation
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat(timespec="seconds")
        active_invites = conn.execute(
            """
            SELECT invitation_id, expires_at FROM organization_invitations
            WHERE organization_id = ? AND email = ? AND state = 'INVITED'
            """,
            (org_id, normalized_invitee),
        ).fetchall()

        for inv in active_invites:
            try:
                exp = datetime.fromisoformat(inv["expires_at"])
            except Exception:
                exp = None

            if exp is not None:
                if exp > now_dt:
                    raise OnboardingError(
                        f"An active invitation already exists for {normalized_invitee}"
                    )
                else:
                    # Mark expired
                    conn.execute(
                        """
                        UPDATE organization_invitations
                        SET state = 'EXPIRED' WHERE invitation_id = ?
                        """,
                        (inv["invitation_id"],),
                    )

        # 4. Create new invitation
        invitation_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        expires_dt = now_dt + timedelta(days=max(1, expiry_days))
        expires_iso = expires_dt.isoformat(timespec="seconds")

        conn.execute(
            """
            INSERT INTO organization_invitations (
                invitation_id, organization_id, organization_name, email, role,
                invited_by_email, token, state, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'INVITED', ?, ?)
            """,
            (
                invitation_id,
                org_id,
                org_name,
                normalized_invitee,
                canonical_role,
                normalized_inviter,
                token,
                now_iso,
                expires_iso,
            ),
        )

        if owns_connection:
            conn.commit()

        # Audit logging
        try:
            audit_service.log_event(
                event_type="INVITATION_CREATED",
                user_id=normalized_inviter,
                action="invitation_created",
                resource_type="invitation",
                resource_id=invitation_id,
                org_id=org_id,
                details={
                    "invitee_email": normalized_invitee,
                    "role": canonical_role,
                    "expires_at": expires_iso,
                },
                status="success",
            )
        except Exception:
            pass

        return InvitationInfo(
            invitation_id=invitation_id,
            organization_id=org_id,
            organization_name=org_name,
            email=normalized_invitee,
            role=canonical_role,
            invited_by_email=normalized_inviter,
            token=token,
            state="INVITED",
            created_at=now_iso,
            expires_at=expires_iso,
        )
    finally:
        if owns_connection:
            conn.close()


def get_invitations(
    organization_id: str,
    *,
    state: str | None = None,
    conn=None,
) -> list[InvitationInfo]:
    """Retrieve invitations scoped strictly to a tenant organization."""
    org_id = str(uuid.UUID(str(organization_id).strip()))
    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        _ensure_tables(conn)
        now_dt = datetime.now(timezone.utc)

        query = "SELECT * FROM organization_invitations WHERE organization_id = ?"
        params: list[Any] = [org_id]
        if state:
            query += " AND state = ?"
            params.append(state.upper())
        query += " ORDER BY created_at DESC"

        rows = conn.execute(query, tuple(params)).fetchall()
        results: list[InvitationInfo] = []

        for r in rows:
            inv_state = r["state"]
            if inv_state == "INVITED":
                try:
                    exp = datetime.fromisoformat(r["expires_at"])
                    if exp <= now_dt:
                        inv_state = "EXPIRED"
                        conn.execute(
                            """
                            UPDATE organization_invitations
                            SET state = 'EXPIRED' WHERE invitation_id = ?
                            """,
                            (r["invitation_id"],),
                        )
                except Exception:
                    pass

            results.append(
                InvitationInfo(
                    invitation_id=r["invitation_id"],
                    organization_id=r["organization_id"],
                    organization_name=r["organization_name"],
                    email=r["email"],
                    role=r["role"],
                    invited_by_email=r["invited_by_email"],
                    token=r["token"],
                    state=inv_state,
                    created_at=r["created_at"],
                    expires_at=r["expires_at"],
                    accepted_at=r["accepted_at"],
                    revoked_at=r["revoked_at"],
                )
            )

        if owns_connection:
            conn.commit()

        return results
    finally:
        if owns_connection:
            conn.close()


def get_invitation_by_token(token: str, *, conn=None) -> InvitationInfo | None:
    """Retrieve invitation by secure token, automatically evaluating expiration."""
    clean_token = str(token or "").strip()
    if not clean_token:
        return None

    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT * FROM organization_invitations WHERE token = ?",
            (clean_token,),
        ).fetchone()

        if not row:
            return None

        inv_state = row["state"]
        now_dt = datetime.now(timezone.utc)
        if inv_state == "INVITED":
            try:
                exp = datetime.fromisoformat(row["expires_at"])
                if exp <= now_dt:
                    inv_state = "EXPIRED"
                    conn.execute(
                        """
                        UPDATE organization_invitations
                        SET state = 'EXPIRED' WHERE invitation_id = ?
                        """,
                        (row["invitation_id"],),
                    )
                    if owns_connection:
                        conn.commit()
            except Exception:
                pass

        return InvitationInfo(
            invitation_id=row["invitation_id"],
            organization_id=row["organization_id"],
            organization_name=row["organization_name"],
            email=row["email"],
            role=row["role"],
            invited_by_email=row["invited_by_email"],
            token=row["token"],
            state=inv_state,
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            accepted_at=row["accepted_at"],
            revoked_at=row["revoked_at"],
        )
    finally:
        if owns_connection:
            conn.close()


def accept_invitation(
    token: str,
    user_email: str,
    *,
    password: str | None = None,
    conn=None,
) -> OnboardingResult:
    """Accept an invitation, creating membership strictly in the invited organization."""
    normalized_email = _normalize_email(user_email)
    invitation = get_invitation_by_token(token, conn=conn)

    if not invitation:
        raise OnboardingError("Invitation not found")

    if invitation.state != "INVITED":
        raise OnboardingError(f"Invitation cannot be accepted in '{invitation.state}' state")

    if invitation.email.lower() != normalized_email:
        raise AuthorizationError(
            f"Invitation was issued for {invitation.email}, not {normalized_email}"
        )

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        _ensure_tables(conn)

        from services.local_auth_service import _password_hash

        # Update or insert user membership bound to invitation's organization_id
        user_row = conn.execute(
            "SELECT password_hash FROM local_auth_users WHERE email = ?",
            (normalized_email,),
        ).fetchone()

        if user_row:
            pwd_hash = user_row["password_hash"]
            if password:
                pwd_hash = _password_hash(password)
            conn.execute(
                """
                UPDATE local_auth_users
                SET role = ?, organization_id = ?, organization_name = ?, password_hash = ?
                WHERE email = ?
                """,
                (
                    invitation.role,
                    invitation.organization_id,
                    invitation.organization_name,
                    pwd_hash,
                    normalized_email,
                ),
            )
        else:
            pwd_hash = _password_hash(password or secrets.token_urlsafe(16))
            conn.execute(
                """
                INSERT INTO local_auth_users (
                    email, password_hash, role, organization_id, organization_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_email,
                    pwd_hash,
                    invitation.role,
                    invitation.organization_id,
                    invitation.organization_name,
                    now,
                ),
            )

        # Mark invitation as accepted
        conn.execute(
            """
            UPDATE organization_invitations
            SET state = 'ACCEPTED', accepted_at = ?
            WHERE invitation_id = ?
            """,
            (now, invitation.invitation_id),
        )

        if owns_connection:
            conn.commit()

        # Audit logging
        try:
            audit_service.log_event(
                event_type="INVITATION_ACCEPTED",
                user_id=normalized_email,
                action="invitation_accepted",
                resource_type="invitation",
                resource_id=invitation.invitation_id,
                org_id=invitation.organization_id,
                details={
                    "organization_name": invitation.organization_name,
                    "role": invitation.role,
                },
                status="success",
            )
        except Exception:
            pass

        org_info = OrganizationInfo(
            organization_id=invitation.organization_id,
            organization_name=invitation.organization_name,
            created_at=now,
            status="active",
            created_by=invitation.invited_by_email,
        )

        return OnboardingResult(
            success=True,
            state=OnboardingState.ONBOARDING_COMPLETE,
            organization=org_info,
            user_email=normalized_email,
            role=invitation.role,
        )
    finally:
        if owns_connection:
            conn.close()


def revoke_invitation(
    invitation_id: str,
    revoker_email: str,
    organization_id: str,
    *,
    conn=None,
) -> bool:
    """Revoke a pending invitation."""
    normalized_revoker = _normalize_email(revoker_email)
    org_id = str(uuid.UUID(str(organization_id).strip()))
    inv_id = str(invitation_id).strip()

    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        _ensure_tables(conn)

        # Verify revoker authority
        revoker_row = conn.execute(
            "SELECT role, organization_id FROM local_auth_users WHERE email = ?",
            (normalized_revoker,),
        ).fetchone()

        if not revoker_row or str(revoker_row["organization_id"]) != org_id:
            raise AuthorizationError("Revoker is not a member of this organization")

        revoker_role = normalize_role(revoker_row["role"])
        if revoker_role not in {"super_admin", "client_admin", "admin"}:
            raise AuthorizationError("Only organization administrators can revoke invitations")

        # Verify invitation belongs to this organization
        inv_row = conn.execute(
            """
            SELECT state, organization_id, email
            FROM organization_invitations WHERE invitation_id = ?
            """,
            (inv_id,),
        ).fetchone()

        if not inv_row:
            raise OnboardingError("Invitation not found")

        if str(inv_row["organization_id"]) != org_id:
            raise AuthorizationError("Cannot revoke invitation from another organization")

        if inv_row["state"] != "INVITED":
            raise OnboardingError(f"Cannot revoke invitation in '{inv_row['state']}' state")

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            """
            UPDATE organization_invitations
            SET state = 'REVOKED', revoked_at = ? WHERE invitation_id = ?
            """,
            (now, inv_id),
        )

        if owns_connection:
            conn.commit()

        # Audit logging
        try:
            audit_service.log_event(
                event_type="INVITATION_REVOKED",
                user_id=normalized_revoker,
                action="invitation_revoked",
                resource_type="invitation",
                resource_id=inv_id,
                org_id=org_id,
                details={"invitee_email": inv_row["email"]},
                status="success",
            )
        except Exception:
            pass

        return True
    finally:
        if owns_connection:
            conn.close()


def is_clean_workspace(organization_id: str, *, conn=None) -> bool:
    """Confirm a newly created tenant has no leaked evidence, spend records, or recommendations."""
    org_id = str(uuid.UUID(str(organization_id).strip()))
    owns_connection = conn is None
    if owns_connection:
        conn = get_db()
    try:
        # Check cloud cost imports
        has_imports = False
        try:
            r = conn.execute(
                "SELECT COUNT(*) as count FROM cloud_cost_import WHERE organization_id = ?",
                (org_id,),
            ).fetchone()
            if r and r["count"] > 0:
                has_imports = True
        except Exception:
            pass

        # Check recommendations
        has_recommendations = False
        try:
            r = conn.execute(
                "SELECT COUNT(*) as count FROM recommendations WHERE org_id = ?",
                (org_id,),
            ).fetchone()
            if r and r["count"] > 0:
                has_recommendations = True
        except Exception:
            pass

        return not has_imports and not has_recommendations
    finally:
        if owns_connection:
            conn.close()
