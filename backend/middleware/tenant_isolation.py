from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from auth.jwt_utils import verify_jwt
from backend.token_store import is_token_revoked


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Initialize request-scoped identity context.
        request.state.current_user = None
        request.state.tenant_id = None

        path = request.url.path
        if path.startswith("/health") or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        auth_header: Optional[str] = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return await call_next(request)

        token = auth_header.split(" ", 1)[1].strip()
        payload = verify_jwt(token)
        if payload == "expired":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        if not payload:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        if is_token_revoked(payload.get("jti")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

        token_tenant = payload.get("tenant_id") or payload.get("org_id")
        header_tenant = request.headers.get("X-Tenant-Id")

        if token_tenant and header_tenant and str(token_tenant) != str(header_tenant):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

        request.state.current_user = payload
        request.state.tenant_id = str(token_tenant) if token_tenant else None

        return await call_next(request)

