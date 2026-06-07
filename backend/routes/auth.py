import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from auth.jwt_utils import create_jwt, verify_jwt
from backend.security import get_current_user, normalize_role
from backend.token_store import is_token_revoked, revoke_token

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


def _load_api_users() -> dict:
    # Example format:
    # API_USERS_JSON={"admin":{"password":"secret","role":"SuperAdmin"}}
    raw = os.getenv("API_USERS_JSON")
    if not raw:
        return {
            "admin": {"password": "admin123", "role": "SuperAdmin"},
            "customer_admin": {"password": "client123", "role": "CustomerAdmin"},
            "finops": {"password": "finops123", "role": "FinOpsManager"},
            "viewer": {"password": "viewer123", "role": "Viewer"},
            "auditor": {"password": "auditor123", "role": "Auditor"},
        }

    import json

    try:
        return json.loads(raw)
    except Exception:
        return {}


@router.post("/auth/login")
def login(payload: LoginRequest):
    users = _load_api_users()
    record = users.get(payload.username)
    if not record or payload.password != str(record.get("password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

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
    decoded = verify_jwt(payload.refresh_token)
    if not decoded or decoded == "expired":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if decoded.get("token_type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    if is_token_revoked(decoded.get("jti")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    # Rotate refresh tokens: revoke old one when exchanging.
    revoke_token(decoded.get("jti"), decoded.get("exp"))

    access_token = create_jwt(
        username=decoded.get("username", "user"),
        role=normalize_role(decoded.get("role", "Viewer")),
        tenant_id=decoded.get("tenant_id") or decoded.get("org_id"),
        token_type="access",
        expires_minutes=60,
    )

    new_refresh_token = create_jwt(
        username=decoded.get("username", "user"),
        role=normalize_role(decoded.get("role", "Viewer")),
        tenant_id=decoded.get("tenant_id") or decoded.get("org_id"),
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
    revoked = 0

    access_token = credentials.credentials if credentials else None
    if access_token:
        decoded_access = verify_jwt(access_token)
        if decoded_access and decoded_access != "expired":
            revoke_token(decoded_access.get("jti"), decoded_access.get("exp"))
            revoked += 1

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
                revoke_token(decoded_refresh.get("jti"), decoded_refresh.get("exp"))
                revoked += 1

    return {"status": "ok", "revoked_tokens": revoked}

