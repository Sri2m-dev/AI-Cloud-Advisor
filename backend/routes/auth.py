from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from auth.jwt_utils import create_jwt, verify_jwt
from backend.api_user_store import (
    APIUserStoreUnavailable,
    is_api_user_active,
    load_api_users,
)
from backend.security import get_current_user, normalize_role
from backend import supabase_auth
from backend.supabase_auth import SupabaseAuthError
from backend.token_store import (
    TokenStoreUnavailable,
    consume_token,
    revoke_token,
    validate_token_claims,
)

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: Optional[str] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


def _load_api_users() -> dict:
    return load_api_users()


def _is_api_user_active(record: dict) -> bool:
    return is_api_user_active(record)


@router.post("/auth/login")
def login(payload: LoginRequest):
    if supabase_auth.enabled():
        try:
            return supabase_auth.sign_in(
                payload.username,
                payload.password,
                payload.tenant_id,
            )
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    try:
        users = _load_api_users()
    except APIUserStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API user authorization store unavailable",
        ) from exc
    record = users.get(payload.username)
    if (
        not isinstance(record, dict)
        or not _is_api_user_active(record)
        or payload.password != str(record.get("password", ""))
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    assigned_tenant = str(record.get("tenant_id") or "").strip()
    if not assigned_tenant or payload.tenant_id != assigned_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant access denied",
        )

    role = normalize_role(str(record.get("role", "Viewer")))
    access_token = create_jwt(
        username=payload.username,
        role=role,
        tenant_id=payload.tenant_id,
        token_type="access",
        expires_minutes=60,
    )
    refresh_token = create_jwt(
        username=payload.username,
        role=role,
        tenant_id=payload.tenant_id,
        token_type="refresh",
        expires_minutes=60 * 24 * 7,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": role,
        "tenant_id": payload.tenant_id,
    }


@router.post("/auth/refresh")
def refresh(payload: RefreshRequest):
    if supabase_auth.enabled():
        try:
            return supabase_auth.refresh_session(payload.refresh_token)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    decoded = verify_jwt(payload.refresh_token)
    if not decoded or decoded == "expired":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if decoded.get("token_type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    try:
        validate_token_claims(decoded.get("jti"), decoded.get("exp"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc

    username = decoded.get("username")
    try:
        users = _load_api_users()
    except APIUserStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API user authorization store unavailable",
        ) from exc
    record = users.get(username) if isinstance(username, str) else None
    if not isinstance(record, dict) or not _is_api_user_active(record):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is no longer active",
        )

    token_tenant = str(decoded.get("tenant_id") or decoded.get("org_id") or "").strip()
    assigned_tenant = str(record.get("tenant_id") or "").strip()
    if not assigned_tenant or token_tenant != assigned_tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant access denied",
        )

    role = normalize_role(str(record.get("role", "Viewer")))

    try:
        consumed = consume_token(decoded.get("jti"), decoded.get("exp"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc
    except TokenStoreUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token revocation store unavailable",
        ) from exc
    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )

    access_token = create_jwt(
        username=username,
        role=role,
        tenant_id=assigned_tenant,
        token_type="access",
        expires_minutes=60,
    )

    new_refresh_token = create_jwt(
        username=username,
        role=role,
        tenant_id=assigned_tenant,
        token_type="refresh",
        expires_minutes=60 * 24 * 7,
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return {
        "username": user.get("username"),
        "role": user.get("role"),
        "tenant_id": user.get("tenant_id") or user.get("org_id"),
        "token_type": user.get("token_type", "access"),
    }


@router.post("/auth/logout")
def logout(
    payload: LogoutRequest,
    user=Depends(get_current_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    if supabase_auth.enabled():
        access_token = credentials.credentials if credentials else None
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
            )
        try:
            supabase_auth.logout(access_token)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        return {"status": "ok", "revoked_tokens": 1}

    revoked = 0

    access_token = credentials.credentials if credentials else None
    if access_token:
        decoded_access = verify_jwt(access_token)
        if decoded_access and decoded_access != "expired":
            try:
                if revoke_token(decoded_access.get("jti"), decoded_access.get("exp")):
                    revoked += 1
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token"
                ) from exc
            except TokenStoreUnavailable as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Token revocation store unavailable",
                ) from exc

    if payload.refresh_token:
        decoded_refresh = verify_jwt(payload.refresh_token)
        if decoded_refresh and decoded_refresh != "expired":
            if (
                (decoded_refresh.get("username") == user.get("username"))
                and (
                    (decoded_refresh.get("tenant_id") or decoded_refresh.get("org_id"))
                    == (user.get("tenant_id") or user.get("org_id"))
                )
            ):
                try:
                    if revoke_token(decoded_refresh.get("jti"), decoded_refresh.get("exp")):
                        revoked += 1
                except ValueError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid refresh token",
                    ) from exc
                except TokenStoreUnavailable as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Token revocation store unavailable",
                    ) from exc

    return {"status": "ok", "revoked_tokens": revoked}


class OwnerWorkflowRequest(BaseModel):
    organization_id: str
    operation_id: str
    correlation_id: str

    model_config = ConfigDict(extra="forbid")


@router.post("/auth/owner-operations/{action}")
def owner_operation(action: str, payload: OwnerWorkflowRequest, user=Depends(get_current_user)):
    """Existing API authentication is account scope, not G08 owner authority."""
    from auth.authenticated_tenant import (
        ProtectedWorkflowUnavailable, api_application_account, require_protected_workflow,
    )

    if action not in {"admit", "revoke", "invalidate", "execute", "reconcile", "reconcile-status"}:
        raise HTTPException(status_code=404, detail="Unknown owner workflow")
    try:
        account = api_application_account(user)
        require_protected_workflow(
            "owner_" + action, account, organization_id=payload.organization_id,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail="Owner workflow scope denied") from error
    except ProtectedWorkflowUnavailable as error:
        raise HTTPException(status_code=503, detail="G08 owner assurance and execution adapter unavailable") from error
