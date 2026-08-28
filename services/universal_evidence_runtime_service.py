"""Application startup boundary for the durable Universal Evidence runtime."""

from __future__ import annotations

import os

from universal_evidence.durable_runtime import DurableRuntimeComposition
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    run_universal_evidence_migrations,
)


def initialize_universal_evidence_runtime(database=None):
    """Migrate then construct; a configured durable runtime never downgrades to memory."""
    configured = database or os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB")
    if not configured:
        if os.getenv("ENVIRONMENT", "").strip().lower() in {"prod", "production"}:
            raise LifecyclePersistenceError(
                "NEXORA_UNIVERSAL_EVIDENCE_DB is required for the production governed runtime"
            )
        return None
    run_universal_evidence_migrations(configured)
    return DurableRuntimeComposition(configured, migrate=False)
