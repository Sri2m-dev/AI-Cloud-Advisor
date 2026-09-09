from __future__ import annotations

from dataclasses import replace

import pytest

from universal_evidence.contracts import EvidenceAnalysisContext
from universal_evidence.identity import (
    BusinessDocumentIdentityCandidate,
    DocumentMatchState,
    RepresentationIdentity,
    assess_document_match,
    deduplicate_documents,
)


def candidate(
    ordinal,
    *,
    invoice="INV-100",
    total="120",
    tax="20",
    lines=(("service", "2", "50", "100"),),
    currency_state="UNRESOLVED",
    currencies=(),
    tenant="tenant",
    media="PDF",
):
    context = EvidenceAnalysisContext("analysis", f"source-{ordinal}", "prospect", "org", tenant)
    representation = RepresentationIdentity(
        f"representation-{ordinal}",
        context,
        f"container-{ordinal}",
        f"set-{ordinal}",
        media,
        f"semantic-{ordinal}",
        (f"source:{ordinal}",),
        f"replay-{ordinal}",
    )
    controls = (
        ("financial.document.subtotal", "100"),
        ("financial.document.total_due", total),
        ("financial.tax", tax),
    )
    return BusinessDocumentIdentityCandidate(
        representation,
        "INVOICE",
        (invoice,) if invoice else (),
        ("2026-08-01",),
        ("supplier",),
        controls,
        currency_state,
        currencies,
        tuple(lines),
        1.0,
        f"candidate-{invoice}-{total}-{lines}-{currency_state}-{currencies}",
    )


def test_same_business_document_across_formats_matches_and_deduplicates():
    left = candidate(1, media="PDF")
    right = candidate(2, media="XLSX")
    match = assess_document_match(left, right)
    view = deduplicate_documents((left, right))
    assert match.state is DocumentMatchState.MATCHED
    assert view.representation_count == 2 and view.business_document_count == 1
    assert len(view.groups[0].representation_ids) == 2
    assert view.financial_authority == "P1/F"


def test_same_amount_with_different_identifier_is_conflict_not_duplicate():
    result = assess_document_match(candidate(1), candidate(2, invoice="INV-200"))
    assert result.state is DocumentMatchState.CONFLICT
    assert "explicit business-document identifiers conflict" in result.conflicts


def test_same_identifier_with_conflicting_total_is_conflict():
    result = assess_document_match(candidate(1), candidate(2, total="121"))
    assert result.state is DocumentMatchState.CONFLICT
    assert "financial controls conflict for the same identifier" in result.conflicts


def test_amount_equality_without_identifier_is_only_possible_match():
    result = assess_document_match(candidate(1, invoice=""), candidate(2, invoice=""))
    assert result.state is DocumentMatchState.POSSIBLE_MATCH


def test_partial_representation_can_be_likely_match_with_strong_identifier():
    complete = candidate(1)
    partial = replace(candidate(2), financial_controls=(), line_signature=())
    assert assess_document_match(complete, partial).state is DocumentMatchState.POSSIBLE_MATCH


def test_explicit_currency_conflict_blocks_match_but_symbol_only_does_not():
    usd = candidate(1, currency_state="CONFIRMED", currencies=("USD",))
    eur = candidate(2, currency_state="CONFIRMED", currencies=("EUR",))
    assert assess_document_match(usd, eur).state is DocumentMatchState.CONFLICT
    unresolved = assess_document_match(candidate(3), candidate(4))
    assert unresolved.state is DocumentMatchState.MATCHED


def test_row_order_differences_are_normalized_by_candidate_construction_contract():
    lines = (("a", "1", "20", "20"), ("b", "2", "40", "80"))
    left = candidate(1, lines=tuple(sorted(lines)))
    right = candidate(2, lines=tuple(sorted(reversed(lines))))
    assert assess_document_match(left, right).state is DocumentMatchState.MATCHED


def test_foreign_tenant_cannot_match():
    with pytest.raises(PermissionError):
        assess_document_match(candidate(1), candidate(2, tenant="foreign"))


def test_deterministic_reconstruction_and_three_representations():
    inputs = (candidate(1), candidate(2, media="XLSX"), candidate(3, media="CSV"))
    first = deduplicate_documents(inputs)
    replay = deduplicate_documents(inputs)
    assert first == replay
    assert first.representation_count == 3 and first.business_document_count == 1


def test_same_filename_is_not_an_identity_signal():
    # Filename is deliberately absent from both identity contracts.
    assert not hasattr(candidate(1).representation, "filename")
