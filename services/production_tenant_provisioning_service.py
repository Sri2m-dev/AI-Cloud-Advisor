"""Offline-testable, fail-closed orchestration for controlled tenant provisioning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

INITIAL_ADMIN_ROLE = "client_admin"
AUTH_PAGE_SIZE = 100
MAX_AUTH_PAGES = 1000
DEMO_ORGANIZATION_ID = "de000000-0000-4000-8000-000000000020"
DEFAULT_ORGANIZATION_ID = "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ProvisioningInputError(ValueError):
    """Invalid or unsafe provisioning input."""


@dataclass(frozen=True, slots=True)
class ProvisioningRequest:
    request_id: str
    organization_id: str
    organization_name: str
    admin_email: str
    role: str = INITIAL_ADMIN_ROLE


@dataclass(frozen=True, slots=True)
class ProvisioningResult:
    request_id: str
    organization_id: str
    organization_name: str
    admin_email: str
    role: str
    classification: str
    steps: dict[str, str]
    reason_code: str | None = None
    timestamp: str = ""

    def operator_evidence(self) -> dict[str, Any]:
        """Return allow-listed OPERATOR_EXECUTION_EVIDENCE, never provider payloads."""
        return {
            "request_id": self.request_id,
            "organization_id": self.organization_id,
            "organization_name": self.organization_name,
            "admin_email": self.admin_email,
            "role": self.role,
            "timestamp": self.timestamp,
            "per_step_status": dict(self.steps),
            "final_classification": self.classification,
        }


def validate_request(
    request_id: str,
    organization_id: str,
    organization_name: str,
    admin_email: str,
) -> ProvisioningRequest:
    request_id = str(request_id or "").strip()
    if not _REQUEST_ID.fullmatch(request_id):
        raise ProvisioningInputError("request_id is invalid")

    raw_organization_id = str(organization_id or "").strip()
    if raw_organization_id.casefold() == "default-org":
        raise ProvisioningInputError("default organization ID is not allowed")
    try:
        normalized_id = str(UUID(raw_organization_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProvisioningInputError("organization_id must be a UUID") from exc
    if normalized_id == DEMO_ORGANIZATION_ID:
        raise ProvisioningInputError("synthetic demo organization ID is not allowed")
    if normalized_id == DEFAULT_ORGANIZATION_ID:
        raise ProvisioningInputError("default organization ID is not allowed")

    organization_name = str(organization_name or "").strip()
    if not 2 <= len(organization_name) <= 100 or any(
        ord(character) < 32 for character in organization_name
    ):
        raise ProvisioningInputError("organization_name is invalid")

    admin_email = str(admin_email or "").strip().lower()
    if not _EMAIL.fullmatch(admin_email):
        raise ProvisioningInputError("admin_email is invalid")

    return ProvisioningRequest(
        request_id=request_id,
        organization_id=normalized_id,
        organization_name=organization_name,
        admin_email=admin_email,
    )


class _RemoteOperationError(RuntimeError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def find_auth_user_by_email(auth_admin, email: str):
    """Scan bounded SDK pages, retaining only the exact matching Auth user."""
    for page in range(1, MAX_AUTH_PAGES + 1):
        users = auth_admin.list_users(page=page, per_page=AUTH_PAGE_SIZE)
        matches = [
            user
            for user in users
            if str(_field(user, "email") or "").strip().lower() == email
        ]
        if len(matches) > 1:
            raise _RemoteOperationError("AUTH_EMAIL_AMBIGUOUS")
        if matches:
            return matches[0]
        if len(users) < AUTH_PAGE_SIZE:
            return None
    raise _RemoteOperationError("AUTH_DIRECTORY_SCAN_LIMIT")


class ProductionTenantProvisioningService:
    """Provision one organization/admin through injected, small adapter APIs."""

    def __init__(self, organizations, profiles, auth_admin, *, clock=None):
        self.organizations = organizations
        self.profiles = profiles
        self.auth_admin = auth_admin
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def provision(self, request: ProvisioningRequest) -> ProvisioningResult:
        if request.role != INITIAL_ADMIN_ROLE:
            raise ProvisioningInputError("initial administrator role is fixed")
        request = validate_request(
            request.request_id,
            request.organization_id,
            request.organization_name,
            request.admin_email,
        )
        steps = {
            "inspect": "NOT_STARTED",
            "organization": "NOT_RUN",
            "profile": "NOT_RUN",
            "auth_invitation": "NOT_RUN",
            "verification": "NOT_RUN",
        }
        try:
            state = self._read_state(request)
        except Exception:
            steps["inspect"] = "FAILED"
            return self._result(request, "REMOTE_OPERATION_FAILED", steps, "INITIAL_READ_FAILED")
        steps["inspect"] = "COMPLETE"

        classification, reason = self._classify(request, state)
        if classification != "NOT_STARTED":
            steps["verification"] = "COMPLETE" if classification == "ALREADY_COMPLETE" else "NOT_RUN"
            return self._result(request, classification, steps, reason)

        try:
            self.organizations.create(
                {
                    "id": request.organization_id,
                    "name": request.organization_name,
                    "status": "active",
                }
            )
            steps["organization"] = "CREATED"
        except Exception:
            steps["organization"] = "UNCERTAIN"
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "ORGANIZATION_WRITE_UNCERTAIN",
            )

        state = self._safe_progress_read(request, steps)
        if state is None or not self._organization_matches(request, state["organization"]):
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "ORGANIZATION_VERIFY_FAILED",
            )
        if state["profile"] is not None or state["auth_user"] is not None:
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "UNEXPECTED_IDENTITY_STATE",
            )
        steps["organization"] = "VERIFIED"

        try:
            self.profiles.create(
                {
                    "email": request.admin_email,
                    "org_id": request.organization_id,
                    "role": INITIAL_ADMIN_ROLE,
                }
            )
            steps["profile"] = "CREATED"
        except Exception:
            steps["profile"] = "UNCERTAIN"
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "PROFILE_WRITE_UNCERTAIN",
            )

        state = self._safe_progress_read(request, steps)
        if state is None or not self._organization_matches(request, state["organization"]):
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "ORGANIZATION_CHANGED_DURING_PROVISIONING",
            )
        if not self._profile_matches(request, state["profile"]):
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "PROFILE_VERIFY_FAILED",
            )
        if state["auth_user"] is not None:
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "AUTH_IDENTITY_APPEARED_UNEXPECTEDLY",
            )
        steps["profile"] = "VERIFIED"

        try:
            invitation = self.auth_admin.invite_user_by_email(request.admin_email)
        except Exception:
            steps["auth_invitation"] = "UNCERTAIN"
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "AUTH_INVITATION_OUTCOME_UNCERTAIN",
            )
        invited_email = str(_field(_field(invitation, "user"), "email") or "").strip().lower()
        if invited_email != request.admin_email:
            steps["auth_invitation"] = "UNCERTAIN"
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "AUTH_INVITATION_IDENTITY_MISMATCH",
            )
        steps["auth_invitation"] = "SENT"

        state = self._safe_progress_read(request, steps)
        if state is None:
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                "FINAL_VERIFICATION_FAILED",
            )
        classification, reason = self._classify(request, state)
        if classification != "ALREADY_COMPLETE":
            return self._result(
                request,
                "PARTIAL_RECONCILIATION_REQUIRED",
                steps,
                reason or "FINAL_STATE_MISMATCH",
            )
        steps["verification"] = "COMPLETE"
        return self._result(request, "COMPLETE", steps)

    def _read_state(self, request):
        organization = self.organizations.get_by_id(request.organization_id)
        profile = self.profiles.get_by_email(request.admin_email)
        auth_user = find_auth_user_by_email(self.auth_admin, request.admin_email)
        return {"organization": organization, "profile": profile, "auth_user": auth_user}

    def _safe_progress_read(self, request, steps):
        try:
            return self._read_state(request)
        except Exception:
            steps["verification"] = "FAILED"
            return None

    def _classify(self, request, state):
        organization = state["organization"]
        profile = state["profile"]
        auth_user = state["auth_user"]
        if organization is not None and not self._organization_matches(request, organization):
            return "HARD_CONFLICT", "ORGANIZATION_ID_NAME_MISMATCH"
        if profile is not None and not self._profile_matches(request, profile):
            return "HARD_CONFLICT", "PROFILE_TENANT_OR_ROLE_MISMATCH"
        if auth_user is not None:
            if organization is not None and profile is not None:
                return "ALREADY_COMPLETE", None
            return "HARD_CONFLICT", "AUTH_IDENTITY_WITHOUT_EXPECTED_PROFILE"
        if organization is not None or profile is not None:
            return "PARTIAL_RECONCILIATION_REQUIRED", "EXISTING_PARTIAL_STATE"
        return "NOT_STARTED", None

    @staticmethod
    def _organization_matches(request, organization):
        return bool(
            organization
            and str(_field(organization, "id")) == request.organization_id
            and str(_field(organization, "name") or "").strip() == request.organization_name
            and str(_field(organization, "status") or "active").strip().lower() == "active"
        )

    @staticmethod
    def _profile_matches(request, profile):
        return bool(
            profile
            and str(_field(profile, "email") or "").strip().lower() == request.admin_email
            and str(_field(profile, "org_id") or "") == request.organization_id
            and str(_field(profile, "role") or "").strip().lower() == INITIAL_ADMIN_ROLE
        )

    def _result(self, request, classification, steps, reason_code=None):
        return ProvisioningResult(
            request_id=request.request_id,
            organization_id=request.organization_id,
            organization_name=request.organization_name,
            admin_email=request.admin_email,
            role=INITIAL_ADMIN_ROLE,
            classification=classification,
            steps=dict(steps),
            reason_code=reason_code,
            timestamp=self.clock().astimezone(timezone.utc).isoformat(),
        )


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)