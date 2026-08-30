"""Application startup boundary for the durable Universal Evidence runtime."""

from __future__ import annotations

import os
from time import perf_counter

from universal_evidence.durable_runtime import DurableRuntimeComposition
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    run_universal_evidence_migrations,
)


def initialize_universal_evidence_runtime(database=None, *, operations=None, context=None):
    """Migrate then construct; a configured durable runtime never downgrades to memory."""
    configured = database or os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB")
    if not configured:
        if os.getenv("ENVIRONMENT", "").strip().lower() in {"prod", "production"}:
            raise LifecyclePersistenceError(
                "NEXORA_UNIVERSAL_EVIDENCE_DB is required for the production governed runtime"
            )
        return None
    started = perf_counter()
    try:
        run_universal_evidence_migrations(configured)
        runtime = DurableRuntimeComposition(
            configured,
            migrate=False,
            operations=operations,
            operation_context=context,
        )
    except Exception:
        if operations is not None and context is not None:
            from universal_evidence.operations import (
                FailureClass,
                GovernedEventType,
                ReasonCode,
                Severity,
            )

            operations.emit(
                GovernedEventType.MIGRATION_FAILED,
                context,
                audit=False,
                severity=Severity.ERROR,
                outcome="FAILED",
                failure_class=FailureClass.MIGRATION_FAILURE,
                reason_code=ReasonCode.MIGRATION_FAILURE,
                duration_ms=(perf_counter() - started) * 1000,
                attributes={"database_identity": _safe_database_identity(configured)},
            )
        raise
    if operations is not None and context is not None:
        from universal_evidence.operations import GovernedEventType

        elapsed = (perf_counter() - started) * 1000
        safe_identity = _safe_database_identity(configured)
        operations.emit(
            GovernedEventType.MIGRATION_COMPLETED,
            context,
            audit=False,
            duration_ms=elapsed,
            attributes={
                "migration_version": "0001",
                "schema_version": "0001",
                "database_identity": safe_identity,
            },
        )
        operations.emit(
            GovernedEventType.PERSISTENCE_INITIALIZED,
            context,
            audit=False,
            duration_ms=elapsed,
            attributes={"database_identity": safe_identity},
        )
    return runtime


def _safe_database_identity(database):
    """Return a support-safe backend identity, never a path or connection string."""
    value = str(database).lower()
    if value.startswith(("postgres://", "postgresql://")):
        return "postgresql"
    if value.startswith("sqlite://") or value.endswith((".db", ".sqlite", ".sqlite3")):
        return "sqlite"
    return "configured-database"
