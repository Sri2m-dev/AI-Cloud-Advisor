"""Server-side verification and tenant resolution for Supabase Auth tokens."""

import json
import os
import ssl
import urllib.error
import urllib.request
from uuid import UUID

import jwt
import psycopg2

from auth.role_constants import ROLES, normalize_role
from backend.token_store import (
    TokenStoreUnavailable,
    is_token_revoked,
    revoke_token,
    validate_token_claims,
)


class SupabaseAuthError(RuntimeError):
    status_code = 503
    detail = "Authentication provider unavailable"


class SupabaseTokenRejected(SupabaseAuthError):
    status_code = 401
    detail = "Invalid or expired authentication token"


class SupabaseCredentialsRejected(SupabaseAuthError):
    status_code = 401
    detail = "Invalid credentials"


class SupabaseMembershipRejected(SupabaseAuthError):
    status_code = 403
    detail = "Active organization membership is required"


class SupabaseAuthUnavailable(SupabaseAuthError):
    status_code = 503
    detail = "Authentication provider unavailable"


def enabled() -> bool:
    return os.getenv("SUPABASE_API_AUTH_ENABLED", "").strip().lower() == "true"


def _configuration() -> tuple[str, str, str, str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    anon_key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    signing_key = os.getenv("JWT_SECRET", "")
    issuer = os.getenv("SUPABASE_JWT_ISSUER", "").strip()
    audience = os.getenv("SUPABASE_JWT_AUDIENCE", "").strip()
    environment = os.getenv("ENVIRONMENT", "").strip().lower()
    verification_mode = os.getenv("NEXORA_CUSTOMER_WORKFLOW_JWT_MODE", "").strip()
    if (
        not url.startswith("https://")
        or not anon_key
        or len(signing_key) < 32
        or not issuer
        or not audience
    ):
        raise SupabaseAuthUnavailable("Supabase API authentication is not configured")
    if verification_mode != "synthetic_hs256" or environment not in {
        "local",
        "test",
        "qualification",
    }:
        raise SupabaseAuthUnavailable(
            "production JWT verification contract is not qualified"
        )
    return url, anon_key, signing_key, issuer, audience


def _request_json(
    method: str,
    path: str,
    *,
    access_token: str | None = None,
    payload: dict | None = None,
    denied_statuses: tuple[int, ...] = (),
) -> object:
    url, anon_key, _, _, _ = _configuration()
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "apikey": anon_key,
        "Accept": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{url}/{path.lstrip('/')}",
        data=data,
        headers=headers,
        method=method,
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    try:
        with opener.open(request, timeout=8) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if path.startswith("auth/v1/token?") and exc.code in {400, 401, 403, 422}:
            raise SupabaseCredentialsRejected() from exc
        if exc.code in denied_statuses:
            raise SupabaseTokenRejected() from exc
        if exc.code in {401, 403}:
            raise SupabaseMembershipRejected() from exc
        raise SupabaseAuthUnavailable() from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SupabaseAuthUnavailable() from exc
    if not body:
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SupabaseAuthUnavailable() from exc


def _decode_access_token(access_token: str) -> dict:
    _, _, signing_key, issuer, audience = _configuration()
    try:
        claims = jwt.decode(
            access_token,
            signing_key,
            algorithms=["HS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["aud", "exp", "iat", "iss", "session_id", "sub"]},
        )
        UUID(str(claims["sub"]))
        UUID(str(claims["session_id"]))
        validate_token_claims(claims["session_id"], claims["exp"])
    except jwt.ExpiredSignatureError as exc:
        raise SupabaseTokenRejected() from exc
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise SupabaseTokenRejected() from exc
    try:
        if is_token_revoked(claims["session_id"]):
            raise SupabaseTokenRejected()
    except TokenStoreUnavailable as exc:
        raise SupabaseAuthUnavailable("Token revocation store unavailable") from exc
    return claims


def _auth_user(access_token: str, subject: str) -> dict:
    user = _request_json(
        "GET",
        "auth/v1/user",
        access_token=access_token,
        denied_statuses=(401, 403),
    )
    if not isinstance(user, dict):
        raise SupabaseAuthUnavailable()
    try:
        user_id = str(UUID(str(user["id"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise SupabaseAuthUnavailable() from exc
    if user_id != subject:
        raise SupabaseTokenRejected()
    email = str(user.get("email") or "").strip().lower()
    if not email:
        raise SupabaseTokenRejected()
    return {"id": user_id, "email": email}


def _identity_membership(access_token: str, subject: str) -> dict:
    dsn = os.getenv("NEXORA_CUSTOMER_WORKFLOW_IDENTITY_DSN", "").strip()
    if not dsn:
        raise SupabaseAuthUnavailable(
            "application identity mapping database is not configured"
        )
    connection = None
    try:
        connection = psycopg2.connect(dsn, connect_timeout=5)
        connection.set_session(readonly=True, autocommit=False)
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('nexora.access_token', %s, true)",
                    (access_token,),
                )
                cursor.execute("SELECT nexora_customer_workflow.verified_subject()")
                if cursor.fetchone() != (subject,):
                    raise SupabaseMembershipRejected()
                cursor.execute(
                    """
                    SELECT auth_user_id::text, org_id::text, tenant_id::text,
                           organization_name, workspace_id, role, status
                    FROM nexora_identity.memberships
                    WHERE auth_user_id = %s::uuid AND status = 'active'
                    ORDER BY org_id
                    LIMIT 2
                    """,
                    (subject,),
                )
                rows = cursor.fetchall()
    except SupabaseAuthError:
        raise
    except psycopg2.Error as exc:
        raise SupabaseAuthUnavailable(
            "application identity mapping is unavailable"
        ) from exc
    finally:
        if connection is not None:
            connection.close()

    if len(rows) != 1:
        raise SupabaseMembershipRejected()
    auth_user_id, organization_id, tenant_id, name, workspace_id, role, status = rows[0]
    try:
        if (
            str(UUID(auth_user_id)) != subject
            or str(UUID(organization_id)) != str(UUID(tenant_id))
            or status != "active"
            or not str(name or "").strip()
        ):
            raise SupabaseMembershipRejected()
        normalized_role = normalize_role(role)
    except (TypeError, ValueError) as exc:
        raise SupabaseMembershipRejected() from exc
    if normalized_role not in ROLES:
        raise SupabaseMembershipRejected()
    return {
        "auth_user_id": subject,
        "org_id": str(UUID(organization_id)),
        "tenant_id": str(UUID(tenant_id)),
        "organization_name": str(name).strip(),
        "workspace_id": workspace_id,
        "role": normalized_role,
        "status": status,
        "permissions": [],
    }


def resolve_access_token(access_token: str) -> dict:
    claims = _decode_access_token(access_token)
    auth_user = _auth_user(access_token, str(claims["sub"]))
    profile = _identity_membership(access_token, auth_user["id"])
    organization_id = profile["org_id"]

    return {
        **claims,
        "sub": auth_user["id"],
        "username": auth_user["email"],
        "email": auth_user["email"],
        "role": profile["role"],
        "tenant_id": organization_id,
        "org_id": organization_id,
        "token_type": "access",
        "jti": str(claims["session_id"]),
        "session_id": str(claims["session_id"]),
        "organization_name": profile["organization_name"],
        "profile": profile,
    }


def _session_response(response: object) -> dict:
    if not isinstance(response, dict):
        raise SupabaseAuthUnavailable()
    access_token = response.get("access_token")
    refresh_token = response.get("refresh_token")
    if not isinstance(access_token, str) or not access_token:
        raise SupabaseAuthUnavailable()
    if not isinstance(refresh_token, str) or not refresh_token:
        raise SupabaseAuthUnavailable()
    user = resolve_access_token(access_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": str(response.get("token_type") or "bearer"),
        "role": user["role"],
        "tenant_id": user["tenant_id"],
    }


def sign_in(email: str, password: str, requested_tenant: str | None = None) -> dict:
    if not email.strip() or not password:
        raise SupabaseTokenRejected()
    response = _request_json(
        "POST",
        "auth/v1/token?grant_type=password",
        payload={"email": email.strip(), "password": password},
    )
    session = _session_response(response)
    if requested_tenant and requested_tenant != session["tenant_id"]:
        logout(session["access_token"], revoke=False)
        raise SupabaseMembershipRejected()
    return session


def refresh_session(refresh_token: str) -> dict:
    if not refresh_token.strip():
        raise SupabaseTokenRejected()
    response = _request_json(
        "POST",
        "auth/v1/token?grant_type=refresh_token",
        payload={"refresh_token": refresh_token},
    )
    return _session_response(response)


def logout(access_token: str, *, revoke: bool = True) -> None:
    claims = _decode_access_token(access_token)
    session_id = str(claims["session_id"])
    if revoke:
        try:
            if not revoke_token(session_id, claims["exp"]):
                raise SupabaseTokenRejected()
        except ValueError as exc:
            raise SupabaseTokenRejected() from exc
        except TokenStoreUnavailable as exc:
            raise SupabaseAuthUnavailable("Token revocation store unavailable") from exc
    _request_json(
        "POST",
        "auth/v1/logout?scope=local",
        access_token=access_token,
        denied_statuses=(401, 403),
    )
