"""PUE-010 non-authoritative shadow integration public API."""

from universal_evidence.shadow.certification import build_certification_report
from universal_evidence.shadow.comparison import compare_with_legacy
from universal_evidence.shadow.models import (
    ActivationReadiness,
    CertificationReport,
    ComparisonState,
    NormalizationBinding,
    PipelineVersions,
    ShadowAnalysisInput,
    ShadowAnalysisResult,
    ShadowComparisonResult,
    ShadowProvenance,
    ShadowQuestionResult,
    ShadowStage,
    ShadowStatus,
    StageResult,
    StageStatus,
)
from universal_evidence.shadow.orchestrator import ShadowOrchestrator
from universal_evidence.shadow.repository import InMemoryShadowRepository

__all__ = [
    "ActivationReadiness",
    "CertificationReport",
    "ComparisonState",
    "InMemoryShadowRepository",
    "NormalizationBinding",
    "PipelineVersions",
    "ShadowAnalysisInput",
    "ShadowAnalysisResult",
    "ShadowComparisonResult",
    "ShadowOrchestrator",
    "ShadowProvenance",
    "ShadowQuestionResult",
    "ShadowStage",
    "ShadowStatus",
    "StageResult",
    "StageStatus",
    "build_certification_report",
    "compare_with_legacy",
]
