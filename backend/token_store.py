import math
import os
from datetime import datetime, timezone

import redis
from redis.exceptions import RedisError

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_KEY_PREFIX = os.getenv("TOKEN_DENYLIST_PREFIX", "denylist:jti")

_redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


class TokenStoreUnavailable(RuntimeError):
    pass


def validate_jti(jti: object) -> str:
    if not isinstance(jti, str) or not jti or jti != jti.strip() or len(jti) > 256:
        raise ValueError("Token JTI is missing or invalid")
    return jti


def _key(jti: str) -> str:
    return f"{REDIS_KEY_PREFIX}:{validate_jti(jti)}"


def _to_exp_datetime(exp) -> datetime:
    if isinstance(exp, datetime):
        if exp.tzinfo is None:
            return exp.replace(tzinfo=timezone.utc)
        return exp.astimezone(timezone.utc)
    if isinstance(exp, bool) or exp is None:
        raise ValueError("Token expiry is missing or invalid")
    try:
        timestamp = float(exp)
        if not math.isfinite(timestamp):
            raise ValueError("Token expiry is missing or invalid")
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, TypeError) as exc:
        raise ValueError("Token expiry is missing or invalid") from exc


def _ttl_seconds(exp) -> int:
    expiry = _to_exp_datetime(exp)
    now = datetime.now(timezone.utc)
    remaining = (expiry - now).total_seconds()
    if remaining <= 0:
        return 0
    return math.ceil(remaining)


def validate_token_claims(jti: object, exp) -> int:
    validate_jti(jti)
    ttl = _ttl_seconds(exp)
    if ttl == 0:
        raise ValueError("Token has expired")
    return ttl


def revoke_token(jti: str, exp) -> bool:
    key = _key(jti)
    ttl = _ttl_seconds(exp)
    if ttl == 0:
        return False
    try:
        _redis_client.set(key, "1", ex=ttl)
    except RedisError as exc:
        raise TokenStoreUnavailable("Token revocation store unavailable") from exc
    return True


def consume_token(jti: str, exp) -> bool:
    key = _key(jti)
    ttl = _ttl_seconds(exp)
    if ttl == 0:
        raise ValueError("Token has expired")
    try:
        consumed = _redis_client.set(key, "1", ex=ttl, nx=True)
    except RedisError as exc:
        raise TokenStoreUnavailable("Token revocation store unavailable") from exc
    return bool(consumed)


def is_token_revoked(jti: str | None) -> bool:
    key = _key(jti)
    try:
        return bool(_redis_client.exists(key))
    except RedisError as exc:
        raise TokenStoreUnavailable("Token revocation store unavailable") from exc