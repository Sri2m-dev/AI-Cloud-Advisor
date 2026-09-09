from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone

import fitz
import pytest
from openpyxl import Workbook

from universal_evidence.containers import decompose_pdf, decompose_xlsx
from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.documents import (
    EvidenceRegion,
    PdfLocation,
    SpreadsheetLocation,
    StructuralLineage,
    StructuralType,
)
from universal_evidence.semantics import (
    SEMANTIC_CLASSIFIER_VERSION,
    SemanticRegionType,
    classify_decomposition,
    classify_region,
    group_evidence_sets,
    normalize_region_features,
)


@dataclass(frozen=True)
class Profile:
    bounded_labels: tuple[str, ...] = ()
    candidate_headers: tuple[str, ...] = ()
    bounded_excerpt: str | None = None
    primitive_distribution: tuple[tuple[str, int], ...] = ()
    number_formats: tuple[str, ...] = ()
    row_count: int | None = None
    column_count: int | None = None


def context(tenant="tenant-a"):
    return EvidenceAnalysisContext("analysis", "source", "prospect", "org", tenant)


def region(
    labels,
    structural_type=StructuralType.TABULAR,
    *,
    row=1,
    page=None,
    tenant="tenant-a",
    confidence=0.99,
):
    ctx = context(tenant)
    container_id = f"container-{tenant}"
    if page is None:
        location = SpreadsheetLocation("sheet-1", row, row + 3, 1, max(2, len(labels)))
        locator = f"sheet-1:{row}"
    else:
        location = PdfLocation(
            f"page-{page}", page, (40.0, float(row), 500.0, float(row + 50)), row
        )
        locator = f"page-{page}:{row}"
    observed = EvidenceRegion(
        ctx,
        container_id,
        None,
        location,
        structural_type,
        locator,
        "synthetic-structure",
        confidence,
        StructuralLineage("authorized:synthetic", container_id, locator),
        tuple(labels),
    )
    profile = Profile(
        bounded_labels=tuple(labels) if page is None else (),
        candidate_headers=tuple(labels) if page is not None else (),
        row_count=4,
        column_count=max(2, len(labels)),
    )
    return observed, profile


def classify(labels, structural_type=StructuralType.TABULAR, **kwargs):
    observed, profile = region(labels, structural_type, **kwargs)
    features = normalize_region_features(observed, profile)
    return observed, features, classify_region(features)


def candidate_types(result):
    return {item.semantic_type for item in result.candidates}


def test_invoice_region_candidates_are_distinct_and_noncanonical():
    _, _, metadata = classify(
        ("Document Number", "Document Date", "Currency"), StructuralType.KEY_VALUE
    )
    _, _, lines = classify(("Description", "Quantity", "Unit Price", "Amount"))
    _, _, summary = classify(("Subtotal", "Tax", "Total"), StructuralType.SUMMARY)
    assert SemanticRegionType.INVOICE_METADATA in candidate_types(metadata)
    assert SemanticRegionType.INVOICE_LINE_ITEMS in candidate_types(lines)
    assert SemanticRegionType.INVOICE_SUMMARY in candidate_types(summary)
    assert not hasattr(lines, "canonical_amount")


def test_license_usage_access_asset_and_context_candidates_are_separate():
    _, _, license_result = classify(("User", "License Tier", "Assigned Status"))
    _, _, usage_result = classify(("Resource", "Usage Metric", "Period", "Quantity"))
    _, _, access_result = classify(("User Account", "Role", "Permission"))
    _, _, asset_result = classify(("Asset", "Version", "Lifecycle"))
    _, _, context_result = classify(("Department", "Owner", "Cost Amount"))
    assert SemanticRegionType.LICENSE_ASSIGNMENT in candidate_types(license_result)
    assert SemanticRegionType.USAGE_DATA in candidate_types(usage_result)
    assert SemanticRegionType.ACCESS_ENTITLEMENT in candidate_types(access_result)
    assert SemanticRegionType.LICENSE_ASSIGNMENT not in candidate_types(access_result)
    assert SemanticRegionType.ASSET_INVENTORY in candidate_types(asset_result)
    assert SemanticRegionType.OWNERSHIP_CONTEXT in candidate_types(context_result)
    assert SemanticRegionType.COST_CONTEXT in candidate_types(context_result)
    assert not hasattr(context_result, "confirmed_owner")


def test_generic_and_ambiguous_regions_remain_unresolved():
    _, _, generic = classify(("Alpha", "Beta", "Gamma"))
    _, _, ambiguous = classify(("Label", "Value"), StructuralType.KEY_VALUE)
    assert generic.decision_state.value == "UNRESOLVED"
    assert ambiguous.decision_state.value == "UNRESOLVED"
    assert SemanticRegionType.GENERIC_TABULAR_EVIDENCE in candidate_types(generic)
    assert SemanticRegionType.GENERIC_KEY_VALUE_EVIDENCE in candidate_types(ambiguous)


def test_false_positive_amount_owner_user_role_and_total_fields_are_resisted():
    _, _, scientific = classify(("Experiment", "Quantity", "Amount"))
    _, _, package = classify(("Package", "Owner", "Version"))
    _, _, directory = classify(("User", "Role", "Department"))
    _, _, monitoring = classify(("Metric", "Total", "Period"))
    assert SemanticRegionType.INVOICE_LINE_ITEMS not in candidate_types(scientific)
    assert SemanticRegionType.OWNERSHIP_CONTEXT not in candidate_types(package)
    assert SemanticRegionType.LICENSE_ASSIGNMENT not in candidate_types(directory)
    assert SemanticRegionType.INVOICE_SUMMARY not in candidate_types(monitoring)


def test_structural_and_semantic_confidence_are_independent_and_explained():
    _, features, result = classify(
        ("Description", "Quantity", "Unit Price", "Amount"), confidence=0.41
    )
    assert features.structural_confidence == 0.41
    assert result.semantic_confidence == 0.82
    assert result.explanation
    assert result.candidates[0].supporting_reasons


def test_classifier_is_deterministic_and_filename_or_format_independent():
    xlsx_region, xlsx_profile = region(
        ("Description", "Quantity", "Unit Price", "Amount"), row=20
    )
    pdf_region, pdf_profile = region(
        ("Description", "Quantity", "Unit Price", "Amount"), page=1, row=200
    )
    xlsx_result = classify_region(normalize_region_features(xlsx_region, xlsx_profile))
    xlsx_replay = classify_region(normalize_region_features(xlsx_region, xlsx_profile))
    pdf_result = classify_region(normalize_region_features(pdf_region, pdf_profile))
    assert xlsx_result.semantic_fingerprint == xlsx_replay.semantic_fingerprint
    assert candidate_types(xlsx_result) == candidate_types(pdf_result)
    assert xlsx_result.classifier_version == SEMANTIC_CLASSIFIER_VERSION


def test_actual_xlsx_and_pdf_profiles_feed_the_same_classifier():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Description", "Quantity", "Unit Price", "Amount"])
    sheet.append(["Item A", 2, 5, 10])
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    xlsx = decompose_xlsx(
        context=context(),
        content=stream.getvalue(),
        admitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_reference="authorized:synthetic",
    )

    pdf_document = fitz.open()
    page = pdf_document.new_page()
    coordinates = (40, 180, 300, 420, 550)
    for x in coordinates:
        page.draw_line((x, 60), (x, 140))
    for y in (60, 100, 140):
        page.draw_line((40, y), (550, y))
    for index, label in enumerate(("Description", "Quantity", "Unit Price", "Amount")):
        page.insert_text((coordinates[index] + 3, 75), label, fontsize=8)
        page.insert_text((coordinates[index] + 3, 115), str(index + 1), fontsize=8)
    pdf_bytes = pdf_document.tobytes()
    pdf_document.close()
    pdf = decompose_pdf(
        context=context(),
        content=pdf_bytes,
        admitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source_reference="authorized:synthetic",
    )
    xlsx_types = candidate_types(classify_decomposition(xlsx)[0])
    pdf_table = next(
        result
        for result in classify_decomposition(pdf)
        if SemanticRegionType.INVOICE_LINE_ITEMS in candidate_types(result)
    )
    assert SemanticRegionType.INVOICE_LINE_ITEMS in xlsx_types
    assert SemanticRegionType.INVOICE_LINE_ITEMS in candidate_types(pdf_table)


def test_invoice_regions_group_while_assignment_remains_separate():
    specs = (
        (("Document Number", "Document Date", "Currency"), StructuralType.KEY_VALUE, 1),
        (("Description", "Quantity", "Unit Price", "Amount"), StructuralType.TABULAR, 10),
        (("Subtotal", "Tax", "Total"), StructuralType.SUMMARY, 20),
        (("User", "License Tier", "Assigned Status"), StructuralType.TABULAR, 30),
    )
    observed = []
    classified = []
    for labels, kind, row in specs:
        item, features, result = classify(labels, kind, row=row)
        observed.append(item)
        classified.append(result)
    grouped = group_evidence_sets(tuple(observed), tuple(classified))
    assert len(grouped) == 2
    assert len(grouped[0].evidence_set.region_ids) == 3
    assert len(grouped[1].evidence_set.region_ids) == 1
    assert all(item.evidence_set.business_document_fingerprint is None for item in grouped)


def test_two_invoice_sequences_form_two_deterministic_sets():
    specs = []
    for base in (1, 40):
        specs.extend(
            (
                (("Invoice Number", "Invoice Date", "Currency"), StructuralType.KEY_VALUE, base),
                (
                    ("Description", "Quantity", "Unit Price", "Amount"),
                    StructuralType.TABULAR,
                    base + 10,
                ),
                (("Subtotal", "Tax", "Total"), StructuralType.SUMMARY, base + 20),
            )
        )
    observed = []
    results = []
    for labels, kind, row in specs:
        item, _, result = classify(labels, kind, row=row)
        observed.append(item)
        results.append(result)
    first = group_evidence_sets(tuple(observed), tuple(results))
    replay = group_evidence_sets(tuple(observed), tuple(results))
    assert len(first) == 2
    assert [item.evidence_set.evidence_set_id for item in first] == [
        item.evidence_set.evidence_set_id for item in replay
    ]


def test_cross_page_complementary_regions_can_group_but_foreign_scope_fails():
    metadata, _, metadata_result = classify(
        ("Invoice Number", "Invoice Date", "Currency"),
        StructuralType.KEY_VALUE,
        page=1,
    )
    lines, _, lines_result = classify(
        ("Description", "Quantity", "Unit Price", "Amount"), page=2
    )
    grouped = group_evidence_sets((metadata, lines), (metadata_result, lines_result))
    assert len(grouped) == 1
    foreign, _, foreign_result = classify(("Alpha", "Beta"), tenant="tenant-b")
    with pytest.raises(PermissionError):
        group_evidence_sets((metadata, foreign), (metadata_result, foreign_result))


def test_no_authority_publication_or_production_activation_surface_exists():
    observed, features, result = classify(("User", "Role", "Permission"))
    grouped = group_evidence_sets((observed,), (result,))
    assert features.region_id == observed.region_id
    assert not hasattr(result, "source_facts")
    assert not hasattr(result, "financial_observations")
    assert not hasattr(result, "optimization_opportunities")
    assert not hasattr(grouped[0], "publication")
