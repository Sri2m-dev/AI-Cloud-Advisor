"""Static ACT-001 readiness classification; it grants no activation authority."""

from universal_evidence.activation.audit import AUDIT_EVENT_TYPES
from universal_evidence.activation.models import (
    ActivationReadinessReport,
    AnalyticalIntentType,
    ArtifactPersistenceClass,
    ReadinessState,
)

PERSISTENCE_CLASSIFICATION = (
    ("raw evidence", ArtifactPersistenceClass.RETENTION_BOUND),
    ("semantic discoveries", ArtifactPersistenceClass.RETENTION_BOUND),
    ("mapping decisions", ArtifactPersistenceClass.AUDIT_REQUIRED),
    ("normalization metadata", ArtifactPersistenceClass.RETENTION_BOUND),
    ("capability assessments", ArtifactPersistenceClass.RETENTION_BOUND),
    ("execution authorizations", ArtifactPersistenceClass.RETENTION_BOUND),
    ("plans and interpretations", ArtifactPersistenceClass.EPHEMERAL),
    ("selected answer history", ArtifactPersistenceClass.OPTIONAL_HISTORY),
    ("activation configuration", ArtifactPersistenceClass.CONFIGURATION),
)

OBSERVABILITY_METRICS = (
    "shadow_runs",
    "visible_runs",
    "successful_pue_routes",
    "fallback_count",
    "blocked_queries",
    "ambiguous_interpretations",
    "normalization_failures",
    "capability_blocks",
    "execution_failures",
    "answer_composition_failures",
    "latency_per_stage",
    "legacy_pue_comparison_distribution",
)


def build_activation_readiness_report():
    blockers = (
        "Production persistence and purge integration are not certified.",
        "Production confirmation UX is not implemented.",
        "Production observability exporters and alerting are not connected.",
        "Production routing, rollback operations, and deployment controls are not certified.",
    )
    return ActivationReadinessReport(
        (
            "PUE-000",
            "PUE-C1",
            "PUE-C2/C2A",
            "PUE-C3",
            "PUE-C4",
            "PUE-C5/C5A",
            "PUE-C6",
            "PUE-C7/C7A",
            "PUE-C8",
            "PUE-C9",
            "PUE-C10@d2a4c225",
        ),
        ReadinessState.READY_FOR_STAGE_2_PILOT,
        "One internal, time-limited prospect or analysis; evidence and capability visibility only.",
        (
            AnalyticalIntentType.COUNT_RECORDS,
            AnalyticalIntentType.TOTAL_MEASURE,
            AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
        ),
        PERSISTENCE_CLASSIFICATION,
        AUDIT_EVENT_TYPES,
        OBSERVABILITY_METRICS,
        blockers,
        "GO for a separately approved Stage 1/2 pilot design; NO-GO for Stage 3/4 activation.",
    )
