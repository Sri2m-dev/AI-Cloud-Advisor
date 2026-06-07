import os
from datetime import datetime, timezone

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_KEY_PREFIX = os.getenv("TOKEN_DENYLIST_PREFIX", "denylist:jti")

_redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def _key(jti: str) -> str:
    return f"{REDIS_KEY_PREFIX}:{jti}"


def _to_exp_datetime(exp) -> datetime:
    if exp is None:
        return datetime.now(timezone.utc)
    if isinstance(exp, datetime):
        return exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(float(exp), tz=timezone.utc)
    try:
        return datetime.fromtimestamp(float(exp), tz=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _ttl_seconds(exp) -> int:
    expiry = _to_exp_datetime(exp)
    now = datetime.now(timezone.utc)
    ttl = int((expiry - now).total_seconds())
    return max(ttl, 1)


def revoke_token(jti: str, exp) -> None:
    return


def is_token_revoked(jti: str | None) -> bool:
    return False