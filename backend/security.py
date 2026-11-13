from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_utils import verify_jwt
from auth.role_constants import normalize_role as normalize_canonical_role
from auth.tenant_authorization import TenantAuthorizationContext, TenantAuthorizationError
from backend.api_user_store import (
    APIUserStoreUnavailable,
    is_api_user_active,
    load_api_users,
)
from backend import supabase_auth
from backend.supabase_auth import SupabaseAuthError
from backend.token_store import (
    TokenStoreUnavailable,
    is_token_revoked,
    validate_token_claims,
)

bearer_scheme = HTTPBearer(auto_error=False)
_load_api_users = load_api_users

ROLE_PERMISSIONS = {
    "super_admin": {
        "tenant:any",
        "cost:read",
        "optimization:read",
        "optimization:run",
        "governance:read",
        "alerts:send",
    },
    "client_admin": {
        "tenant:scoped",
        "cost:read",
        "optimization:read",
        "optimization:run",
        "governance:read",
        "alerts:send",
    },
    "finance": {
        "tenant:scoped",
        "cost:read",
        "optimization:read",
        "optimization:run",
    },
    "viewer": {
        "tenant:scoped",
        "cost:read",
        "optimization:read",
        "governance:read",
    },
    "auditor": {
        "tenant:scoped",
        "governance:read",
    },
}


def normalize_role(role: str) -> str:
    return normalize_canonical_role(role)


def _resolve_authorized_user(user_data: dict) -> dict:
    username = user_data.get("username")
    if not isinstance(username, str) or not username.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token identity",
        )
    try:
        record = _load_api_users().get(username)
    except APIUserStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API user authorization store unavailable",
        ) from exc

    if not isinstance(record, dict) or not is_api_user_active(record):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is no longer active",
        )

    token_tenant = str(user_data.get("tenant_id") or user_data.get("org_id") or "").strip()
    assigned_tenant = str(record.get("tenant_id") or "").strip()
    if not assigned_tenant or token_tenant != assigned_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant access denied",
        )

    user_data["role"] = normalize_role(str(record.get("role", "Viewer")))
    user_data["tenant_id"] = assigned_tenant
    user_data["org_id"] = assigned_tenant
    return user_data


def _ensure_token_active(payload: dict) -> None:
    try:
        validate_token_claims(payload.get("jti"), payload.get("exp"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    try:
        if is_token_revoked(payload.get("jti")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )
    except TokenStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token revocation store unavailable",
        ) from exc


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    # Prefer middleware-decoded user context
    state_user = getattr(request.state, "current_user", None)

    if state_user:
        if state_user.get("token_type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Wrong token type",
            )
        if supabase_auth.enabled():
            return state_user
        if not getattr(request.state, "token_revocation_checked", False):
            _ensure_token_active(state_user)
        return _resolve_authorized_user(state_user)

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    if supabase_auth.enabled():
        try:
            return supabase_auth.resolve_access_token(credentials.credentials)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

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
    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong token type",
        )

    _ensure_token_active(payload)

    return _resolve_authorized_user(payload)


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
    try:
        context = TenantAuthorizationContext.from_principal(
            user,
            source_boundary="api",
        )
        middleware_tenant = getattr(request.state, "tenant_id", None)
        chosen_tenant = middleware_tenant or context.tenant_id
        context.authorize(
            organization_id=context.organization_id,
            tenant_id=x_tenant_id or chosen_tenant,
        )
        return context.tenant_id
    except TenantAuthorizationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if "is required" in detail
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
