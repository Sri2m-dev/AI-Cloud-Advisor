from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from auth.jwt_utils import verify_jwt
from backend import supabase_auth
from backend.supabase_auth import SupabaseAuthError
from backend.token_store import (
    TokenStoreUnavailable,
    is_token_revoked,
    validate_token_claims,
)


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Initialize request-scoped identity context.
        request.state.current_user = None
        request.state.tenant_id = None
        request.state.token_revocation_checked = False

        path = request.url.path
        if path.startswith("/health") or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        auth_header: Optional[str] = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return await call_next(request)

        token = auth_header.split(" ", 1)[1].strip()
        if supabase_auth.enabled():
            try:
                payload = supabase_auth.resolve_access_token(token)
            except SupabaseAuthError as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"detail": exc.detail},
                )
            token_tenant = payload["tenant_id"]
            header_tenant = request.headers.get("X-Tenant-Id")
            if header_tenant and str(token_tenant) != str(header_tenant):
                return JSONResponse(status_code=403, content={"detail": "Tenant mismatch"})
            request.state.current_user = payload
            request.state.tenant_id = str(token_tenant)
            request.state.token_revocation_checked = True
            return await call_next(request)

        payload = verify_jwt(token)
        if payload == "expired":
            return JSONResponse(status_code=401, content={"detail": "Token expired"})
        if not payload:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        if payload.get("token_type") != "access":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Wrong token type"},
            )
        try:
            validate_token_claims(payload.get("jti"), payload.get("exp"))
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid token"},
            )
        try:
            if is_token_revoked(payload.get("jti")):
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Token revoked"},
                )
        except TokenStoreUnavailable:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Token revocation store unavailable"},
            )
        request.state.token_revocation_checked = True

        token_tenant = payload.get("tenant_id") or payload.get("org_id")
        header_tenant = request.headers.get("X-Tenant-Id")

        if token_tenant and header_tenant and str(token_tenant) != str(header_tenant):
            return JSONResponse(status_code=403, content={"detail": "Tenant mismatch"})

        request.state.current_user = payload
        request.state.tenant_id = str(token_tenant) if token_tenant else None

        return await call_next(request)
