from dataclasses import asdict
from datetime import datetime, timezone

import pytest

from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.documents import (
    EvidenceDocument,
    EvidenceRegion,
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
    structural_fingerprint,
)


def context(tenant="tenant-a"):
    return EvidenceAnalysisContext("analysis", "source", "prospect", "org", tenant)


def container(ctx=None, filename="alpha.xlsx", state=StructuralState.DISCOVERED):
    return UploadContainer(
        ctx or context(),
        "a" * 64,
        "XLSX",
        12,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        "authorized:evidence",
        security_status=state,
        filename=filename,
    )


def document(item=None, locator="workbook:part:0"):
    item = item or container()
    lineage = StructuralLineage("authorized:evidence", item.container_id, locator)
    return EvidenceDocument(
        item.context, item.container_id, 0, locator, "workbook", "XLSX", lineage, 1.0
    )


def region(doc=None, start_row=1, state=StructuralState.DISCOVERED):
    doc = doc or document()
    location = SpreadsheetLocation("sheet-1", start_row, start_row + 4, 1, 3)
    lineage = StructuralLineage("authorized:evidence", doc.container_id, f"sheet-1:{start_row}:1")
    return EvidenceRegion(
        doc.context,
        doc.container_id,
        doc.document_id,
        location,
        StructuralType.TABULAR,
        "profile:region",
        "STRUCTURAL_DISCOVERY",
        0.9,
        lineage,
        ("field-a", "field-b"),
        status=state,
    )


def test_container_identity_is_replay_stable_and_filename_independent():
    first = container(filename="first.xlsx")
    second = container(filename="renamed.xlsx")
    assert first.content_fingerprint == second.content_fingerprint
    assert first.container_id == second.container_id


def test_container_identity_is_tenant_scoped_and_resolution_fails_closed():
    first = container(context("tenant-a"))
    foreign = container(context("tenant-b"))
    assert first.container_id != foreign.container_id
    with pytest.raises(PermissionError):
        assert_same_scope(first.context, foreign.context)


def test_document_and_region_identities_are_structural_and_deterministic():
    first_document = document()
    reconstructed_document = document()
    assert first_document == reconstructed_document
    first = region(first_document)
    reconstructed = region(reconstructed_document)
    different = region(first_document, start_row=2)
    assert first.region_id == reconstructed.region_id
    assert first.structural_fingerprint == reconstructed.structural_fingerprint
    assert first.region_id != different.region_id
    assert first.structural_fingerprint != different.structural_fingerprint


def test_container_supports_multiple_documents_and_document_multiple_regions():
    item = container()
    documents = (document(item, "part:0"), document(item, "part:1"))
    regions = (region(documents[0], 1), region(documents[0], 20))
    assert len({candidate.document_id for candidate in documents}) == 2
    assert all(candidate.document_id == documents[0].document_id for candidate in regions)


def test_structure_remains_neutral_and_semantic_confidence_is_separate():
    observed = region()
    assert set(StructuralType) == {
        StructuralType.TABULAR,
        StructuralType.KEY_VALUE,
        StructuralType.SUMMARY,
        StructuralType.TEXT,
        StructuralType.FORM,
        StructuralType.UNKNOWN,
    }
    semantic = SemanticEvidenceSet(
        "set-1",
        observed.context,
        (observed.region_id,),
        None,
        SemanticDecisionState.UNRESOLVED,
        0.2,
        (observed.region_id,),
    )
    assert observed.structural_confidence == 0.9
    assert semantic.semantic_confidence == 0.2


def test_unknown_partial_and_quarantined_states_are_explicit():
    unknown = region(state=StructuralState.UNRESOLVED)
    partial = region(state=StructuralState.PARTIAL)
    quarantined = region(state=StructuralState.QUARANTINED)
    assert unknown.structural_type is StructuralType.TABULAR
    assert partial.status is StructuralState.PARTIAL
    assert not quarantined.publishable
    assert not container(state=StructuralState.QUARANTINED).publishable


def test_security_and_resource_diagnostics_are_explicit():
    diagnostics = (SecurityDiagnostic(SecurityFinding.MACRO_PRESENT, "active content detected"),)
    resources = ResourceDiagnostics(
        12,
        expanded_size=100,
        limit_exceeded=True,
        partial_reason="expanded limit",
    )
    item = UploadContainer(
        context(), "b" * 64, "XLSX", 12, datetime.now(timezone.utc), "source-ref",
        security_status=StructuralState.QUARANTINED,
        security_diagnostics=diagnostics,
        resource_diagnostics=resources,
    )
    assert item.security_diagnostics[0].finding is SecurityFinding.MACRO_PRESENT
    assert item.resource_diagnostics.limit_exceeded
    assert not item.publishable


def test_lineage_is_bounded_and_reaches_source_and_container():
    observed = region()
    payload = repr(asdict(observed.lineage))
    assert observed.lineage.source_reference == "authorized:evidence"
    assert observed.lineage.container_id == observed.container_id
    assert "invoice text" not in payload
    assert not hasattr(observed, "raw_content")


def test_canonical_serialization_is_order_independent_and_rejects_raw_objects():
    assert structural_fingerprint("test", {"b": 2, "a": 1}) == structural_fingerprint(
        "test", {"a": 1, "b": 2}
    )
    with pytest.raises(TypeError):
        structural_fingerprint("test", object())
