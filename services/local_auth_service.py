"""Non-production local authentication with tenant-bound, hashed credentials."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from auth.role_constants import normalize_role
from database.db import get_db
from services.runtime_configuration import is_valid_supabase_configuration

DEFAULT_ADMIN_EMAIL = "admin@company.com"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_ROLE = "super_admin"
DEFAULT_ORGANIZATION_ID = "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"
DEFAULT_ORGANIZATION_NAME = "Default Org"
DEFAULT_PERSONA_PASSWORD = "persona123"

LOCAL_PERSONAS = (
    (DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_ROLE, DEFAULT_ADMIN_PASSWORD),
    ("ceo@company.com", "executive", DEFAULT_PERSONA_PASSWORD),
    ("cio@company.com", "cio", DEFAULT_PERSONA_PASSWORD),
    ("cto@company.com", "cio", DEFAULT_PERSONA_PASSWORD),
    ("finance@company.com", "finance", DEFAULT_PERSONA_PASSWORD),
    ("auditor@company.com", "auditor", DEFAULT_PERSONA_PASSWORD),
    ("operations@company.com", "operations", DEFAULT_PERSONA_PASSWORD),
)

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


def local_auth_enabled(
    *,
    environment: str | None = None,
    auth_mode: str | None = None,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
) -> bool:
    runtime_environment = str(
        environment
        or os.getenv("ENVIRONMENT")
        or os.getenv("CLOUD_ADVISOR_ENV", "development")
    ).strip().lower()
    if runtime_environment == "production":
        return False
    mode = str(auth_mode if auth_mode is not None else os.getenv("AUTH_MODE", "")).strip().lower()
    if mode in {"dev", "demo", "local"}:
        return True
    url = os.getenv("SUPABASE_URL", "") if supabase_url is None else supabase_url
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY", "")
    ) if supabase_key is None else supabase_key
    return not is_valid_supabase_configuration(url, key)


def ensure_default_tenant_administrator(*, environment: str | None = None) -> bool:
    """Create the default local administrator if absent; never replace credentials."""
    if not local_auth_enabled(environment=environment):
        return False
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


def ensure_nonproduction_personas(*, environment: str | None = None) -> int:
    """Reconcile deterministic local personas only in an authorized non-production mode."""
    if not local_auth_enabled(environment=environment):
        return 0
    conn = get_db()
    changed = 0
    try:
        _ensure_schema(conn)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for email, role, password in LOCAL_PERSONAS:
            canonical_role = normalize_role(role)
            row = conn.execute(
                """SELECT password_hash, role, organization_id, organization_name
                   FROM local_auth_users WHERE email = ?""",
                (email,),
            ).fetchone()
            valid = bool(
                row
                and _password_matches(password, row["password_hash"])
                and normalize_role(row["role"]) == canonical_role
                and row["organization_id"] == DEFAULT_ORGANIZATION_ID
                and row["organization_name"] == DEFAULT_ORGANIZATION_NAME
            )
            if valid:
                continue
            payload = (
                _password_hash(password),
                canonical_role,
                DEFAULT_ORGANIZATION_ID,
                DEFAULT_ORGANIZATION_NAME,
                now,
                email,
            )
            if row:
                conn.execute(
                    """UPDATE local_auth_users
                       SET password_hash = ?, role = ?, organization_id = ?,
                           organization_name = ?, created_at = ? WHERE email = ?""",
                    payload,
                )
            else:
                conn.execute(
                    """INSERT INTO local_auth_users
                       (password_hash, role, organization_id, organization_name, created_at, email)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    payload,
                )
            changed += 1
        conn.commit()
        return changed
    finally:
        conn.close()


def authenticate_local_user(
    email: str, password: str, *, environment: str | None = None
) -> LocalUser | None:
    if not local_auth_enabled(environment=environment):
        return None
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
            role=normalize_role(row["role"]),
            organization_id=row["organization_id"],
            organization_name=row["organization_name"],
        )
    finally:
        conn.close()
