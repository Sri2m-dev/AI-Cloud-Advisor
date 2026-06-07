
import jwt
import os
from datetime import datetime, timedelta
from uuid import uuid4

SECRET_KEY = os.getenv("JWT_SECRET", "dev-insecure-secret")  # Use env var in production!


def create_jwt(username, role, tenant_id=None, token_type="access", expires_minutes=60):
    payload = {
        "jti": str(uuid4()),
        "username": username,
        "role": role,
        "token_type": token_type,
        "tenant_id": tenant_id,
        "org_id": tenant_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token


def verify_jwt(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return "expired"
    except jwt.InvalidTokenError:
        return None

