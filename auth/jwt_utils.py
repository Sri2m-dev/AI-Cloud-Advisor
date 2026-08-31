
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

_DEVELOPMENT_SECRET = secrets.token_urlsafe(48)


def _secret_key():
    configured = os.getenv("JWT_SECRET")
    if configured:
        return configured
    if os.getenv("ENVIRONMENT", "").strip().lower() in {"prod", "production"}:
        raise RuntimeError("JWT_SECRET is required in production")
    return _DEVELOPMENT_SECRET


def create_jwt(username, role, tenant_id=None, token_type="access", expires_minutes=60):
    payload = {
        "jti": str(uuid4()),
        "username": username,
        "role": role,
        "token_type": token_type,
        "tenant_id": tenant_id,
        "org_id": tenant_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
    }
    token = jwt.encode(payload, _secret_key(), algorithm="HS256")
    return token


def verify_jwt(token):
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return "expired"
    except jwt.InvalidTokenError:
        return None

