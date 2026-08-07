"""Non-production local authentication with tenant-bound, hashed credentials."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from database.db import get_db

DEFAULT_ADMIN_EMAIL = "admin@company.com"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_ROLE = "super_admin"
DEFAULT_ORGANIZATION_ID = "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"
DEFAULT_ORGANIZATION_NAME = "Default Org"

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000


@dataclass(frozen=True)
class LocalUser:
    email: str
    role: str
    organization_id: str
    organization_name: str


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected_hex = encoded.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (AttributeError, TypeError, ValueError):
        return False


def _ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS local_auth_users (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            organization_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def ensure_default_tenant_administrator() -> bool:
    """Create the default local administrator if absent; never replace credentials."""
    conn = get_db()
    try:
        _ensure_schema(conn)
        existing = conn.execute(
            "SELECT 1 FROM local_auth_users WHERE email = ?", (DEFAULT_ADMIN_EMAIL,)
        ).fetchone()
        if existing:
            conn.commit()
            return False
        conn.execute(
            """
            INSERT INTO local_auth_users (
                email, password_hash, role, organization_id, organization_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_ADMIN_EMAIL,
                _password_hash(DEFAULT_ADMIN_PASSWORD),
                DEFAULT_ADMIN_ROLE,
                DEFAULT_ORGANIZATION_ID,
                DEFAULT_ORGANIZATION_NAME,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def authenticate_local_user(email: str, password: str) -> LocalUser | None:
    conn = get_db()
    try:
        _ensure_schema(conn)
        row = conn.execute(
            """
            SELECT email, password_hash, role, organization_id, organization_name
            FROM local_auth_users WHERE email = ?
            """,
            ((email or "").strip().lower(),),
        ).fetchone()
        if not row or not _password_matches(password or "", row["password_hash"]):
            return None
        return LocalUser(
            email=row["email"],
            role=row["role"],
            organization_id=row["organization_id"],
            organization_name=row["organization_name"],
        )
    finally:
        conn.close()
