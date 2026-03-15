import base64
import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
from cryptography.fernet import Fernet
from psycopg2.extras import RealDictCursor


SQLITE_DB_PATH = "cloud_advisor.db"
FERNET_KEY_ENV = "CLOUD_ADVISOR_CREDENTIAL_KEY"
FERNET_KEY_FILE = Path(__file__).resolve().parent.parent / ".streamlit" / "credential.key"


def get_account_limit(plan="Free"):
    limits = {
        "Free": 1,
        "Starter": 3,
        "Pro": 10,
        "Enterprise": 50,
    }
    return limits.get(plan, 1)


def get_pg_connection():
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "cloud_advisor"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "password"),
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        cursor_factory=RealDictCursor,
    )


def init_pg_db():
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            company VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS cloud_accounts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            provider VARCHAR(20),
            account_id VARCHAR(255),
            credentials_encrypted TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS cost_data (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES cloud_accounts(id),
            date DATE,
            service VARCHAR(255),
            cost NUMERIC
        );
        CREATE TABLE IF NOT EXISTS predictions (
            id SERIAL PRIMARY KEY,
            account_id INTEGER REFERENCES cloud_accounts(id),
            month VARCHAR(7),
            predicted_cost NUMERIC
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def get_db():
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn, table_name):
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def _ensure_column(conn, table_name, column_name, column_sql):
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def _billing_duplicate_count_query():
    return """
        SELECT COALESCE(SUM(row_count - 1), 0)
        FROM (
            SELECT COUNT(*) AS row_count
            FROM billing_data
            GROUP BY COALESCE(date, ''), COALESCE(account, ''), COALESCE(service, '')
            HAVING COUNT(*) > 1
        ) duplicate_groups
    """


def _cleanup_billing_duplicates(conn):
    duplicate_count = conn.execute(_billing_duplicate_count_query()).fetchone()[0]
    try:
        conn.execute(
            """
            DELETE FROM billing_data
            WHERE rowid NOT IN (
                SELECT MAX(rowid)
                FROM billing_data
                GROUP BY COALESCE(date, ''), COALESCE(account, ''), COALESCE(service, '')
            )
            """
        )
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            return 0
        raise
    return int(duplicate_count or 0)


def _ensure_forecast_notes_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS forecast_notes (
            username TEXT,
            forecast_date TEXT,
            note TEXT,
            PRIMARY KEY (username, forecast_date)
        )
        """
    )


def _ensure_users_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )


def _ensure_audit_log_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _ensure_billing_data_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_data (
            date TEXT,
            account TEXT,
            service TEXT,
            cost REAL,
            synced_at TEXT
        )
        """
    )
    _ensure_column(conn, "billing_data", "date", "TEXT")
    _ensure_column(conn, "billing_data", "account", "TEXT")
    _ensure_column(conn, "billing_data", "service", "TEXT")
    _ensure_column(conn, "billing_data", "cost", "REAL")
    _ensure_column(conn, "billing_data", "synced_at", "TEXT")
    _cleanup_billing_duplicates(conn)
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_data_account_date_service
        ON billing_data(account, date, service)
        """
    )


def _ensure_cloud_sync_runs_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cloud_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cloud_account_id INTEGER NOT NULL,
            username TEXT,
            provider TEXT,
            status TEXT,
            trigger_type TEXT,
            started_at TEXT,
            finished_at TEXT,
            duration_seconds REAL,
            record_count INTEGER,
            coverage_start TEXT,
            coverage_end TEXT,
            error_code TEXT,
            error_message TEXT,
            metadata TEXT
        )
        """
    )
    _ensure_column(conn, "cloud_sync_runs", "username", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "provider", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "status", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "trigger_type", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "started_at", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "finished_at", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "duration_seconds", "REAL")
    _ensure_column(conn, "cloud_sync_runs", "record_count", "INTEGER")
    _ensure_column(conn, "cloud_sync_runs", "coverage_start", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "coverage_end", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "error_code", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "error_message", "TEXT")
    _ensure_column(conn, "cloud_sync_runs", "metadata", "TEXT")


def _ensure_recommendations_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            account_identifier TEXT,
            provider TEXT,
            category TEXT,
            title TEXT,
            description TEXT,
            status TEXT DEFAULT 'new',
            owner TEXT,
            priority TEXT,
            estimated_savings REAL,
            realized_savings REAL DEFAULT 0,
            due_date TEXT,
            dismiss_reason TEXT,
            source TEXT,
            resource TEXT,
            created_at TEXT,
            updated_at TEXT,
            completed_at TEXT
        )
        """
    )
    _ensure_column(conn, "recommendations", "username", "TEXT")
    _ensure_column(conn, "recommendations", "account_identifier", "TEXT")
    _ensure_column(conn, "recommendations", "provider", "TEXT")
    _ensure_column(conn, "recommendations", "category", "TEXT")
    _ensure_column(conn, "recommendations", "title", "TEXT")
    _ensure_column(conn, "recommendations", "description", "TEXT")
    _ensure_column(conn, "recommendations", "status", "TEXT DEFAULT 'new'")
    _ensure_column(conn, "recommendations", "owner", "TEXT")
    _ensure_column(conn, "recommendations", "priority", "TEXT")
    _ensure_column(conn, "recommendations", "estimated_savings", "REAL")
    _ensure_column(conn, "recommendations", "realized_savings", "REAL DEFAULT 0")
    _ensure_column(conn, "recommendations", "due_date", "TEXT")
    _ensure_column(conn, "recommendations", "dismiss_reason", "TEXT")
    _ensure_column(conn, "recommendations", "source", "TEXT")
    _ensure_column(conn, "recommendations", "resource", "TEXT")
    _ensure_column(conn, "recommendations", "created_at", "TEXT")
    _ensure_column(conn, "recommendations", "updated_at", "TEXT")
    _ensure_column(conn, "recommendations", "completed_at", "TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_recommendations_identity
        ON recommendations(username, source, category, title, resource)
        """
    )


def _ensure_recommendation_events_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id INTEGER NOT NULL,
            username TEXT,
            action TEXT,
            old_value TEXT,
            new_value TEXT,
            notes TEXT,
            created_at TEXT
        )
        """
    )
    _ensure_column(conn, "recommendation_events", "recommendation_id", "INTEGER")
    _ensure_column(conn, "recommendation_events", "username", "TEXT")
    _ensure_column(conn, "recommendation_events", "action", "TEXT")
    _ensure_column(conn, "recommendation_events", "old_value", "TEXT")
    _ensure_column(conn, "recommendation_events", "new_value", "TEXT")
    _ensure_column(conn, "recommendation_events", "notes", "TEXT")
    _ensure_column(conn, "recommendation_events", "created_at", "TEXT")


def _ensure_cloud_accounts_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cloud_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            provider TEXT,
            account_name TEXT,
            account_identifier TEXT,
            details TEXT,
            credentials_encrypted TEXT,
            sync_enabled INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            last_synced_at TEXT,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_column(conn, "cloud_accounts", "username", "TEXT")
    _ensure_column(conn, "cloud_accounts", "provider", "TEXT")
    _ensure_column(conn, "cloud_accounts", "account_name", "TEXT")
    _ensure_column(conn, "cloud_accounts", "account_identifier", "TEXT")
    _ensure_column(conn, "cloud_accounts", "details", "TEXT")
    _ensure_column(conn, "cloud_accounts", "credentials_encrypted", "TEXT")
    _ensure_column(conn, "cloud_accounts", "sync_enabled", "INTEGER DEFAULT 1")
    _ensure_column(conn, "cloud_accounts", "status", "TEXT DEFAULT 'pending'")
    _ensure_column(conn, "cloud_accounts", "last_synced_at", "TEXT")
    _ensure_column(conn, "cloud_accounts", "last_error", "TEXT")
    _ensure_column(conn, "cloud_accounts", "validation_status", "TEXT DEFAULT 'pending'")
    _ensure_column(conn, "cloud_accounts", "validation_message", "TEXT")
    _ensure_column(conn, "cloud_accounts", "health_score", "INTEGER DEFAULT 0")
    _ensure_column(conn, "cloud_accounts", "last_validation_at", "TEXT")
    _ensure_column(conn, "cloud_accounts", "sync_frequency_hours", "INTEGER DEFAULT 24")
    _ensure_column(conn, "cloud_accounts", "coverage_start", "TEXT")
    _ensure_column(conn, "cloud_accounts", "coverage_end", "TEXT")
    _ensure_column(conn, "cloud_accounts", "last_sync_duration_seconds", "REAL")
    _ensure_column(conn, "cloud_accounts", "last_sync_record_count", "INTEGER DEFAULT 0")
    _ensure_column(conn, "cloud_accounts", "next_sync_at", "TEXT")
    _ensure_column(conn, "cloud_accounts", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")


def create_tables():
    conn = get_db()
    _ensure_billing_data_table(conn)
    _ensure_users_table(conn)
    _ensure_audit_log_table(conn)
    _ensure_forecast_notes_table(conn)
    _ensure_cloud_accounts_table(conn)
    _ensure_cloud_sync_runs_table(conn)
    _ensure_recommendations_table(conn)
    _ensure_recommendation_events_table(conn)
    conn.commit()
    conn.close()


def _normalize_fernet_key(raw_key):
    key_bytes = raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key
    try:
        Fernet(key_bytes)
        return key_bytes
    except Exception:
        digest = hashlib.sha256(key_bytes).digest()
        return base64.urlsafe_b64encode(digest)


def _get_fernet():
    configured_key = os.getenv(FERNET_KEY_ENV)
    if configured_key:
        return Fernet(_normalize_fernet_key(configured_key))
    if not FERNET_KEY_FILE.exists():
        FERNET_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        FERNET_KEY_FILE.write_bytes(Fernet.generate_key())
    return Fernet(_normalize_fernet_key(FERNET_KEY_FILE.read_bytes().strip()))


def encrypt_credentials(credentials):
    payload = json.dumps(credentials).encode("utf-8")
    return _get_fernet().encrypt(payload).decode("utf-8")


def decrypt_credentials(token):
    if not token:
        return {}
    payload = _get_fernet().decrypt(token.encode("utf-8"))
    return json.loads(payload.decode("utf-8"))


def save_forecast_note(username, forecast_date, note):
    conn = get_db()
    _ensure_forecast_notes_table(conn)
    conn.execute(
        "REPLACE INTO forecast_notes (username, forecast_date, note) VALUES (?, ?, ?)",
        (username, forecast_date, note),
    )
    conn.commit()
    conn.close()


def load_forecast_note(username, forecast_date):
    conn = get_db()
    _ensure_forecast_notes_table(conn)
    cur = conn.execute(
        "SELECT note FROM forecast_notes WHERE username = ? AND forecast_date = ?",
        (username, forecast_date),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""


def save_cost_data(provider, cost_df, account_name=None):
    if not isinstance(cost_df, pd.DataFrame) or cost_df.empty:
        return
    conn = get_db()
    _ensure_billing_data_table(conn)
    synced_at = datetime.utcnow().isoformat(timespec="seconds")
    account_value = account_name or provider
    for _, row in cost_df.iterrows():
        date_value = row.get("date") or row.get("Date") or synced_at[:10]
        service_value = row.get("Service") or row.get("service") or provider
        cost_value = row.get("Cost") if row.get("Cost") is not None else row.get("cost", 0)
        conn.execute(
            """
            INSERT INTO billing_data (date, account, service, cost, synced_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(account, date, service)
            DO UPDATE SET cost = excluded.cost, synced_at = excluded.synced_at
            """,
            (str(date_value), account_value, str(service_value), float(cost_value or 0), synced_at),
        )
    conn.commit()
    conn.close()


def insert_cost(account, service, cost, date=None):
    conn = get_db()
    _ensure_billing_data_table(conn)
    conn.execute(
        """
        INSERT INTO billing_data (date, account, service, cost, synced_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(account, date, service)
        DO UPDATE SET cost = excluded.cost, synced_at = excluded.synced_at
        """,
        (
            date or datetime.utcnow().date().isoformat(),
            account,
            service,
            cost,
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def get_billing_duplicate_count():
    conn = get_db()
    _ensure_billing_data_table(conn)
    duplicate_count = conn.execute(_billing_duplicate_count_query()).fetchone()[0]
    conn.close()
    return int(duplicate_count or 0)


def cleanup_billing_data_duplicates():
    conn = get_db()
    _ensure_billing_data_table(conn)
    removed_count = _cleanup_billing_duplicates(conn)
    conn.commit()
    conn.close()
    return removed_count


def add_user(username, password, role):
    conn = get_db()
    _ensure_users_table(conn)
    conn.execute(
        "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, password, role),
    )
    conn.commit()
    conn.close()


def get_user(username):
    conn = get_db()
    _ensure_users_table(conn)
    cur = conn.execute("SELECT username, password, role FROM users WHERE username = ?", (username,))
    user = cur.fetchone()
    conn.close()
    return user


def get_user_role(username):
    user = get_user(username) if username else None
    return user[2] if user else "user"


def get_recommendation(recommendation_id):
    conn = get_db()
    _ensure_recommendations_table(conn)
    row = conn.execute(
        """
        SELECT id, username, account_identifier, provider, category, title, description,
               status, owner, priority, estimated_savings, realized_savings, due_date,
               dismiss_reason, source, resource, created_at, updated_at, completed_at
        FROM recommendations
        WHERE id = ?
        """,
        (recommendation_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def can_manage_recommendation(recommendation, acting_username, action="view"):
    if not recommendation or not acting_username:
        return False

    role = get_user_role(acting_username)
    if role in {"admin", "premium"}:
        return True

    owner = recommendation.get("owner")
    if action == "view":
        return owner == acting_username or not owner
    if action == "accept":
        return owner in {None, "", acting_username}
    return owner == acting_username


def log_audit_event(username, action, details=None):
    conn = get_db()
    _ensure_audit_log_table(conn)
    conn.execute(
        "INSERT INTO audit_log (username, action, details) VALUES (?, ?, ?)",
        (username, action, details),
    )
    conn.commit()
    conn.close()


def save_cloud_account(username, provider, account_name, account_identifier, credentials, details=None):
    conn = get_db()
    _ensure_cloud_accounts_table(conn)
    encrypted = encrypt_credentials(credentials)
    now = datetime.utcnow().isoformat(timespec="seconds")
    details = details or {}
    validation_status = details.get("status", "pending")
    validation_message = details.get("message")
    health_score = int(details.get("health_score", 0) or 0)
    sync_frequency_hours = int(details.get("sync_frequency_hours", 24) or 24)
    existing = conn.execute(
        "SELECT id FROM cloud_accounts WHERE username = ? AND provider = ? AND account_identifier = ?",
        (username, provider, account_identifier),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE cloud_accounts
            SET account_name = ?, details = ?, credentials_encrypted = ?, sync_enabled = 1,
                status = 'pending', last_error = NULL, validation_status = ?, validation_message = ?,
                health_score = ?, last_validation_at = ?, sync_frequency_hours = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                account_name,
                json.dumps(details),
                encrypted,
                validation_status,
                validation_message,
                health_score,
                now,
                sync_frequency_hours,
                now,
                existing[0],
            ),
        )
        account_id = existing[0]
    else:
        cur = conn.execute(
            """
            INSERT INTO cloud_accounts (
                username, provider, account_name, account_identifier, details,
                credentials_encrypted, sync_enabled, status, validation_status,
                validation_message, health_score, last_validation_at, sync_frequency_hours,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 'pending', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                provider,
                account_name,
                account_identifier,
                json.dumps(details),
                encrypted,
                validation_status,
                validation_message,
                health_score,
                now,
                sync_frequency_hours,
                now,
                now,
            ),
        )
        account_id = cur.lastrowid
    conn.commit()
    conn.close()
    return account_id


def list_cloud_accounts(username=None):
    conn = get_db()
    _ensure_cloud_accounts_table(conn)
    if username:
        cur = conn.execute(
            """
            SELECT id, username, provider, account_name, account_identifier, status,
                   sync_enabled, last_synced_at, last_error, validation_status,
                   validation_message, health_score, last_validation_at,
                   sync_frequency_hours, coverage_start, coverage_end,
                   last_sync_duration_seconds, last_sync_record_count,
                   next_sync_at, created_at, updated_at
            FROM cloud_accounts
            WHERE username = ?
            ORDER BY created_at DESC
            """,
            (username,),
        )
    else:
        cur = conn.execute(
            """
            SELECT id, username, provider, account_name, account_identifier, status,
                   sync_enabled, last_synced_at, last_error, validation_status,
                   validation_message, health_score, last_validation_at,
                   sync_frequency_hours, coverage_start, coverage_end,
                   last_sync_duration_seconds, last_sync_record_count,
                   next_sync_at, created_at, updated_at
            FROM cloud_accounts
            ORDER BY created_at DESC
            """
        )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_cloud_account(account_id):
    conn = get_db()
    _ensure_cloud_accounts_table(conn)
    row = conn.execute("SELECT * FROM cloud_accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_cloud_account_sync_status(account_id, status, last_error=None, synced_at=None):
    conn = get_db()
    _ensure_cloud_accounts_table(conn)
    effective_sync_time = synced_at if status == "synced" else None
    conn.execute(
        """
        UPDATE cloud_accounts
        SET status = ?, last_error = ?, last_synced_at = COALESCE(?, last_synced_at), updated_at = ?
        WHERE id = ?
        """,
        (status, last_error, effective_sync_time, datetime.utcnow().isoformat(timespec="seconds"), account_id),
    )
    conn.commit()
    conn.close()


def update_cloud_account_health(
    account_id,
    validation_status=None,
    validation_message=None,
    health_score=None,
    last_validation_at=None,
    coverage_start=None,
    coverage_end=None,
    next_sync_at=None,
    sync_frequency_hours=None,
):
    conn = get_db()
    _ensure_cloud_accounts_table(conn)
    conn.execute(
        """
        UPDATE cloud_accounts
        SET validation_status = COALESCE(?, validation_status),
            validation_message = COALESCE(?, validation_message),
            health_score = COALESCE(?, health_score),
            last_validation_at = COALESCE(?, last_validation_at),
            coverage_start = COALESCE(?, coverage_start),
            coverage_end = COALESCE(?, coverage_end),
            next_sync_at = COALESCE(?, next_sync_at),
            sync_frequency_hours = COALESCE(?, sync_frequency_hours),
            updated_at = ?
        WHERE id = ?
        """,
        (
            validation_status,
            validation_message,
            health_score,
            last_validation_at,
            coverage_start,
            coverage_end,
            next_sync_at,
            sync_frequency_hours,
            datetime.utcnow().isoformat(timespec="seconds"),
            account_id,
        ),
    )
    conn.commit()
    conn.close()


def record_cloud_account_sync_result(
    account_id,
    status,
    synced_at=None,
    last_error=None,
    duration_seconds=None,
    record_count=None,
    coverage_start=None,
    coverage_end=None,
    next_sync_at=None,
):
    conn = get_db()
    _ensure_cloud_accounts_table(conn)
    effective_sync_time = synced_at if status == "synced" else None
    conn.execute(
        """
        UPDATE cloud_accounts
        SET status = ?,
            last_error = ?,
            last_synced_at = COALESCE(?, last_synced_at),
            last_sync_duration_seconds = COALESCE(?, last_sync_duration_seconds),
            last_sync_record_count = COALESCE(?, last_sync_record_count),
            coverage_start = COALESCE(?, coverage_start),
            coverage_end = COALESCE(?, coverage_end),
            next_sync_at = COALESCE(?, next_sync_at),
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            last_error,
            effective_sync_time,
            duration_seconds,
            record_count,
            coverage_start,
            coverage_end,
            next_sync_at,
            datetime.utcnow().isoformat(timespec="seconds"),
            account_id,
        ),
    )
    conn.commit()
    conn.close()


def create_sync_run(cloud_account_id, username=None, provider=None, trigger_type="scheduled", metadata=None):
    conn = get_db()
    _ensure_cloud_sync_runs_table(conn)
    started_at = datetime.utcnow().isoformat(timespec="seconds")
    cur = conn.execute(
        """
        INSERT INTO cloud_sync_runs (
            cloud_account_id, username, provider, status, trigger_type, started_at, metadata
        ) VALUES (?, ?, ?, 'running', ?, ?, ?)
        """,
        (
            cloud_account_id,
            username,
            provider,
            trigger_type,
            started_at,
            json.dumps(metadata or {}),
        ),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def finish_sync_run(
    run_id,
    status,
    finished_at=None,
    duration_seconds=None,
    record_count=None,
    coverage_start=None,
    coverage_end=None,
    error_code=None,
    error_message=None,
    metadata=None,
):
    conn = get_db()
    _ensure_cloud_sync_runs_table(conn)
    conn.execute(
        """
        UPDATE cloud_sync_runs
        SET status = ?,
            finished_at = ?,
            duration_seconds = ?,
            record_count = ?,
            coverage_start = ?,
            coverage_end = ?,
            error_code = ?,
            error_message = ?,
            metadata = COALESCE(?, metadata)
        WHERE id = ?
        """,
        (
            status,
            finished_at or datetime.utcnow().isoformat(timespec="seconds"),
            duration_seconds,
            record_count,
            coverage_start,
            coverage_end,
            error_code,
            error_message,
            json.dumps(metadata) if metadata is not None else None,
            run_id,
        ),
    )
    conn.commit()
    conn.close()


def list_sync_runs(cloud_account_id=None, username=None, limit=20):
    conn = get_db()
    _ensure_cloud_sync_runs_table(conn)
    query = """
        SELECT id, cloud_account_id, username, provider, status, trigger_type,
               started_at, finished_at, duration_seconds, record_count,
               coverage_start, coverage_end, error_code, error_message, metadata
        FROM cloud_sync_runs
    """
    conditions = []
    params = []
    if cloud_account_id is not None:
        conditions.append("cloud_account_id = ?")
        params.append(cloud_account_id)
    if username is not None:
        conditions.append("username = ?")
        params.append(username)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    rows = [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]
    conn.close()
    return rows


def add_recommendation_event(recommendation_id, username, action, old_value=None, new_value=None, notes=None):
    conn = get_db()
    _ensure_recommendation_events_table(conn)
    conn.execute(
        """
        INSERT INTO recommendation_events (
            recommendation_id, username, action, old_value, new_value, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            recommendation_id,
            username,
            action,
            old_value,
            new_value,
            notes,
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def list_recommendation_events(recommendation_id, limit=20):
    conn = get_db()
    _ensure_recommendation_events_table(conn)
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, recommendation_id, username, action, old_value, new_value, notes, created_at
            FROM recommendation_events
            WHERE recommendation_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (recommendation_id, limit),
        ).fetchall()
    ]
    conn.close()
    return rows


def save_recommendation(
    username,
    category,
    title,
    description,
    source,
    resource=None,
    account_identifier=None,
    provider=None,
    owner=None,
    priority="medium",
    estimated_savings=None,
    due_date=None,
):
    conn = get_db()
    _ensure_recommendations_table(conn)
    now = datetime.utcnow().isoformat(timespec="seconds")
    existing = conn.execute(
        """
        SELECT id, status
        FROM recommendations
        WHERE username = ? AND source = ? AND category = ? AND title = ? AND COALESCE(resource, '') = COALESCE(?, '')
        """,
        (username, source, category, title, resource),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE recommendations
            SET description = ?, account_identifier = ?, provider = ?, owner = COALESCE(?, owner),
                priority = COALESCE(?, priority), estimated_savings = COALESCE(?, estimated_savings),
                due_date = COALESCE(?, due_date), updated_at = ?
            WHERE id = ?
            """,
            (
                description,
                account_identifier,
                provider,
                owner,
                priority,
                estimated_savings,
                due_date,
                now,
                existing[0],
            ),
        )
        recommendation_id = existing[0]
    else:
        cur = conn.execute(
            """
            INSERT INTO recommendations (
                username, account_identifier, provider, category, title, description, status,
                owner, priority, estimated_savings, due_date, source, resource, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                account_identifier,
                provider,
                category,
                title,
                description,
                owner,
                priority,
                estimated_savings,
                due_date,
                source,
                resource,
                now,
                now,
            ),
        )
        recommendation_id = cur.lastrowid
    conn.commit()
    conn.close()
    return recommendation_id


def list_recommendations(username=None, status=None, source=None, limit=100):
    conn = get_db()
    _ensure_recommendations_table(conn)
    query = """
        SELECT id, username, account_identifier, provider, category, title, description,
               status, owner, priority, estimated_savings, realized_savings, due_date,
               dismiss_reason, source, resource, created_at, updated_at, completed_at
        FROM recommendations
    """
    conditions = []
    params = []
    if username is not None:
        conditions.append("username = ?")
        params.append(username)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY updated_at DESC, created_at DESC LIMIT ?"
    params.append(limit)
    rows = [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]
    conn.close()
    return rows


def update_recommendation_status(
    recommendation_id,
    status,
    username=None,
    owner=None,
    dismiss_reason=None,
    realized_savings=None,
    notes=None,
):
    conn = get_db()
    _ensure_recommendations_table(conn)
    row = conn.execute(
        "SELECT status, owner, realized_savings, dismiss_reason FROM recommendations WHERE id = ?",
        (recommendation_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False
    recommendation = {
        "id": recommendation_id,
        "status": row[0],
        "owner": row[1],
        "realized_savings": row[2],
        "dismiss_reason": row[3],
    }
    action_name = "accept" if status == "accepted" else f"status:{status}"
    if not can_manage_recommendation(recommendation, username, action=action_name):
        conn.close()
        return False
    previous_status = row[0]
    effective_owner = owner
    if status == "accepted" and not effective_owner and not row[1]:
        effective_owner = username
    completed_at = datetime.utcnow().isoformat(timespec="seconds") if status == "completed" else None
    conn.execute(
        """
        UPDATE recommendations
        SET status = ?, owner = COALESCE(?, owner), dismiss_reason = COALESCE(?, dismiss_reason),
            realized_savings = COALESCE(?, realized_savings), completed_at = COALESCE(?, completed_at), updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            effective_owner,
            dismiss_reason,
            realized_savings,
            completed_at,
            datetime.utcnow().isoformat(timespec="seconds"),
            recommendation_id,
        ),
    )
    conn.commit()
    conn.close()
    add_recommendation_event(
        recommendation_id,
        username,
        action="status_changed",
        old_value=previous_status,
        new_value=status,
        notes=notes or dismiss_reason,
    )
    return True


def update_recommendation_details(
    recommendation_id,
    username=None,
    owner=None,
    priority=None,
    due_date=None,
    notes=None,
):
    conn = get_db()
    _ensure_recommendations_table(conn)
    row = conn.execute(
        "SELECT owner, priority, due_date FROM recommendations WHERE id = ?",
        (recommendation_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False
    recommendation = {
        "id": recommendation_id,
        "owner": row[0],
        "priority": row[1],
        "due_date": row[2],
    }
    if not can_manage_recommendation(recommendation, username, action="details"):
        conn.close()
        return False

    role = get_user_role(username)
    effective_owner = owner if role in {"admin", "premium"} else row[0]

    old_snapshot = {
        "owner": row[0],
        "priority": row[1],
        "due_date": row[2],
    }
    new_snapshot = {
        "owner": effective_owner if effective_owner is not None else row[0],
        "priority": priority if priority is not None else row[1],
        "due_date": due_date if due_date is not None else row[2],
    }

    conn.execute(
        """
        UPDATE recommendations
        SET owner = COALESCE(?, owner),
            priority = COALESCE(?, priority),
            due_date = COALESCE(?, due_date),
            updated_at = ?
        WHERE id = ?
        """,
        (
            effective_owner,
            priority,
            due_date,
            datetime.utcnow().isoformat(timespec="seconds"),
            recommendation_id,
        ),
    )
    conn.commit()
    conn.close()
    add_recommendation_event(
        recommendation_id,
        username,
        action="details_updated",
        old_value=json.dumps(old_snapshot),
        new_value=json.dumps(new_snapshot),
        notes=notes,
    )
    return True


def get_connected_account_count(username=None):
    conn = get_db()
    _ensure_cloud_accounts_table(conn)
    if username:
        cur = conn.execute("SELECT COUNT(*) FROM cloud_accounts WHERE username = ?", (username,))
    else:
        cur = conn.execute("SELECT COUNT(*) FROM cloud_accounts")
    count = cur.fetchone()[0]
    conn.close()
    return count


create_tables()
