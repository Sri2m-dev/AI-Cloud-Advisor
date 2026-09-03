import os

import psycopg2


class DatabaseConfigurationError(RuntimeError):
    """Raised when the legacy PostgreSQL adapter lacks required configuration."""


def get_connection():
    password = os.getenv("PGPASSWORD", "").strip()
    if not password:
        environment = os.getenv("ENVIRONMENT", os.getenv("CLOUD_ADVISOR_ENV", "development"))
        raise DatabaseConfigurationError(
            "PGPASSWORD is required for the PostgreSQL connection "
            f"in {environment.strip().lower() or 'development'}"
        )
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        database=os.getenv("PGDATABASE", "AI-Cloud-Advisor-Dev"),
        user=os.getenv("PGUSER", "postgres"),
        password=password,
    )

