"""Universal document and structural region contract surface."""

from universal_evidence.documents.identity import structural_fingerprint
from universal_evidence.documents.models import (
    DelimitedLocation,
    EvidenceDocument,
    EvidenceRegion,
    PdfLocation,
    ResourceDiagnostics,
    SecurityDiagnostic,
    SecurityFinding,
    SemanticDecisionState,
    SemanticEvidenceSet,
    SpreadsheetLocation,
    StructuralLineage,
    StructuralState,
    StructuralType,
    UploadContainer,
    assert_same_scope,
)

__all__ = [
    "DelimitedLocation",
    "EvidenceDocument",
    "EvidenceRegion",
    "PdfLocation",
    "ResourceDiagnostics",
    "SecurityDiagnostic",
    "SecurityFinding",
    "SemanticDecisionState",
    "SemanticEvidenceSet",
    "SpreadsheetLocation",
    "StructuralLineage",
    "StructuralState",
    "StructuralType",
    "UploadContainer",
    "assert_same_scope",
    "structural_fingerprint",
]
