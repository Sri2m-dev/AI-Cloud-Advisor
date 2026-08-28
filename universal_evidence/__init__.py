"""Architecture contracts for the non-authoritative Universal Evidence Engine."""

from universal_evidence.durable_runtime import (
    DurableActivationRepository,
    DurableAggregationRepository,
    DurableAnalyticalPlanRepository,
    DurableAnswerReferenceRepository,
    DurableLineageRepository,
    DurableMappingDecisionRepository,
    DurableNormalizationAdapter,
    DurableReconciliationRepository,
    DurableRuntimeComposition,
)
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    LifecycleRecord,
    LifecycleScope,
    SQLiteLifecycleRepository,
    run_universal_evidence_migrations,
)

__all__ = [
    "LifecyclePersistenceError",
    "LifecycleRecord",
    "LifecycleScope",
    "SQLiteLifecycleRepository",
    "run_universal_evidence_migrations",
    "DurableActivationRepository",
    "DurableAggregationRepository",
    "DurableAnalyticalPlanRepository",
    "DurableAnswerReferenceRepository",
    "DurableMappingDecisionRepository",
    "DurableLineageRepository",
    "DurableNormalizationAdapter",
    "DurableReconciliationRepository",
    "DurableRuntimeComposition",
]
