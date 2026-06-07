from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_utils import verify_jwt
from backend.token_store import is_token_revoked
from core.user_profile import get_user_profile

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_ALIASES = {
    "global_admin": "SuperAdmin",
    "client_admin": "CustomerAdmin",
    "finops": "FinOpsManager",
    "admin": "SuperAdmin",
    "viewer": "Viewer",
    "auditor": "Auditor",
}

ROLE_PERMISSIONS = {
    "SuperAdmin": {
        "tenant:any",
        "cost:read",
        "optimization:read",
        "optimization:run",
        "governance:read",
        "alerts:send",
    },
    "CustomerAdmin": {
        "tenant:scoped",
        "cost:read",
        "optimization:read",
        "optimization:run",
        "governance:read",
        "alerts:send",
    },
    "FinOpsManager": {
        "tenant:scoped",
        "cost:read",
        "optimization:read",
        "optimization:run",
    },
    "Viewer": {
        "tenant:scoped",
        "cost:read",
        "optimization:read",
        "governance:read",
    },
    "Auditor": {
        "tenant:scoped",
        "governance:read",
    },
}


def normalize_role(role: str) -> str:
    raw = str(role or "").strip()

    if raw in ROLE_PERMISSIONS:
        return raw

    lowered = raw.lower()
    mapped = ROLE_ALIASES.get(lowered)

    if mapped:
        return mapped

    return raw


def _resolve_user_role(user_data: dict) -> str:
    """
    Try Supabase profile first.
    Fall back to JWT role if profile doesn't exist.
    """

    try:
        user_profile = None

        if user_data.get("id"):
            user_profile = get_user_profile(user_id=user_data.get("id"))

        elif user_data.get("username"):
            user_profile = get_user_profile(email=user_data.get("username"))

        if user_profile and "role" in user_profile:
            return normalize_role(user_profile["role"])

    except Exception:
        # Ignore Supabase lookup failures
        pass

    return normalize_role(user_data.get("role", "Viewer"))


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    # Prefer middleware-decoded user context
    state_user = getattr(request.state, "current_user", None)

    if state_user:
        state_user["role"] = _resolve_user_role(state_user)
        return state_user

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    payload = verify_jwt(credentials.credentials)

    if payload == "expired":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    try:
        if is_token_revoked(payload.get("jti")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token revocation store unavailable",
        ) from exc

    payload["role"] = _resolve_user_role(payload)

    return payload


def require_role(allowed_roles):
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    normalized_allowed = {
        normalize_role(r)
        for r in allowed_roles
    }

    def _checker(user=Depends(get_current_user)):
        role = normalize_role(user.get("role", ""))

        if role not in normalized_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )

        return user

    return _checker


def require_roles(allowed_roles: List[str]):
    return require_role(allowed_roles)


def tenant_guard(
    request: Request,
    user=Depends(get_current_user),
    x_tenant_id: Optional[str] = Header(
        default=None,
        alias="X-Tenant-Id",
    ),
):
    token_tenant = user.get("tenant_id") or user.get("org_id")
    middleware_tenant = getattr(request.state, "tenant_id", None)

    chosen_tenant = middleware_tenant or token_tenant

    if not chosen_tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant is required",
        )

    if x_tenant_id and str(chosen_tenant) != str(x_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch",
        )

    return str(chosen_tenant)