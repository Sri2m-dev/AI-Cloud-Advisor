from __future__ import annotations

import os

from universal_evidence.persistence import SQLiteLifecycleRepository

from .governance import GovernedOptimizationRepository
from .publication import CanonicalOptimizationRepository


def configured_optimization_authority(database=None):
    location = str(database or os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB") or "").strip()
    if not location:
        raise RuntimeError("durable optimization database is required")
    return (
        GovernedOptimizationRepository(SQLiteLifecycleRepository(location)),
        CanonicalOptimizationRepository(location),
    )
