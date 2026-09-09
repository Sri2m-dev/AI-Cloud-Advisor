"""Deterministic candidate identity for many representations of one document."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from universal_evidence.documents import assert_same_scope, structural_fingerprint
from universal_evidence.financial.models import FinancialConcept

IDENTITY_VERSION = "pue-011g.business-document.v1"


class DocumentMatchState(str, Enum):
    MATCHED = "MATCHED"
    LIKELY_MATCH = "LIKELY_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"


class IdentityDecisionType(str, Enum):
    CONFIRM_MATCH = "CONFIRM_MATCH"
    REJECT_MATCH = "REJECT_MATCH"
    OVERRIDE_GROUPING = "OVERRIDE_GROUPING"
    SPLIT_GROUP = "SPLIT_GROUP"
    MERGE_GROUP = "MERGE_GROUP"


@dataclass(frozen=True, slots=True)
class RepresentationIdentity:
    representation_id: str
    context: object
    container_id: str
    evidence_set_id: str
    media_type: str
    semantic_identity: str | None
    source_lineage: tuple[str, ...]
    source_replay_fingerprint: str


@dataclass(frozen=True, slots=True)
class BusinessDocumentIdentityCandidate:
    representation: RepresentationIdentity
    semantic_document_type: str
    business_identifiers: tuple[str, ...]
    dates_or_periods: tuple[str, ...]
    party_candidates: tuple[str, ...]
    financial_controls: tuple[tuple[str, str], ...]
    currency_state: str
    currencies: tuple[str, ...]
    line_signature: tuple[tuple[str, str, str, str], ...]
    completeness: float
    candidate_fingerprint: str


@dataclass(frozen=True, slots=True)
class DocumentMatchAssessment:
    left_representation_id: str
    right_representation_id: str
    state: DocumentMatchState
    score: float
    match_reasons: tuple[str, ...]
    conflicts: tuple[str, ...]
    algorithm_version: str = IDENTITY_VERSION


@dataclass(frozen=True, slots=True)
class DocumentIdentityDecision:
    decision_type: IdentityDecisionType
    representation_ids: tuple[str, ...]
    actor: str
    reason: str
    decided_at: str
    supersedes: str | None = None


@dataclass(frozen=True, slots=True)
class BusinessDocumentGroup:
    business_document_fingerprint: str
    representation_ids: tuple[str, ...]
    preferred_representation_id: str
    decision_state: DocumentMatchState
    assessments: tuple[DocumentMatchAssessment, ...] = ()


@dataclass(frozen=True, slots=True)
class DeduplicatedDocumentView:
    groups: tuple[BusinessDocumentGroup, ...]
    representation_count: int
    business_document_count: int
    financial_authority: str = "P1/F"


def identity_candidates(
    *, decomposition, adapted_documents
) -> tuple[BusinessDocumentIdentityCandidate, ...]:
    """Create identities without filenames, positions, or raw hashes as business keys."""
    output = []
    for adapted in adapted_documents:
        evidence = adapted.evidence
        analysis = adapted.analysis
        representation_fingerprint = structural_fingerprint(
            IDENTITY_VERSION + ".representation",
            decomposition.container.container_id,
            evidence.evidence_set_id,
            decomposition.container.container_type,
            tuple(evidence.region_ids),
        )
        representation = RepresentationIdentity(
            "representation-" + representation_fingerprint[:24],
            decomposition.container.context,
            decomposition.container.container_id,
            evidence.evidence_set_id,
            decomposition.container.container_type,
            None,
            tuple(value.reference for value in evidence.values)
            + tuple(line.row_reference for line in evidence.lines),
            decomposition.container.content_fingerprint,
        )
        identifiers = tuple(
            sorted(
                {
                    _identifier(value.value)
                    for value in evidence.values
                    if "invoice" in _normalize(value.label)
                    and ("number" in _normalize(value.label) or "no" in _normalize(value.label))
                    and _identifier(value.value)
                }
            )
        )
        dates = tuple(
            sorted(
                str(value.value)
                for value in evidence.values
                if "date" in _normalize(value.label) or "period" in _normalize(value.label)
            )
        )
        controls = tuple(
            sorted(
                (item.concept.value, _number(item.normalized_amount))
                for item in analysis.concept_observations
                if item.concept
                in {FinancialConcept.SUBTOTAL, FinancialConcept.TAX, FinancialConcept.TOTAL_DUE}
                and item.normalized_amount is not None
            )
        )
        line_signature = tuple(
            sorted(
                (
                    _description(line.description_reference),
                    _number(line.quantity),
                    _number(line.unit_price),
                    _number(line.amount),
                )
                for line in evidence.lines
            )
        )
        currency_state = (
            "CONFIRMED"
            if analysis.currency.governed
            else (
                "MIXED"
                if analysis.currency.conflicted and analysis.currency.currencies
                else "UNRESOLVED"
            )
        )
        business_fingerprint = structural_fingerprint(
            IDENTITY_VERSION + ".candidate",
            "INVOICE",
            identifiers,
            dates,
            controls,
            line_signature,
            currency_state,
            analysis.currency.currencies,
        )
        completeness = (
            sum(bool(item) for item in (identifiers, dates, controls, line_signature)) / 4
        )
        output.append(
            BusinessDocumentIdentityCandidate(
                representation,
                "INVOICE",
                identifiers,
                dates,
                (),
                controls,
                currency_state,
                analysis.currency.currencies,
                line_signature,
                completeness,
                business_fingerprint,
            )
        )
    return tuple(output)


def assess_document_match(left, right) -> DocumentMatchAssessment:
    assert_same_scope(left.representation.context, right.representation.context)
    reasons, conflicts = [], []
    score = 0.0
    if left.semantic_document_type != right.semantic_document_type:
        conflicts.append("semantic document types conflict")
    if left.business_identifiers and right.business_identifiers:
        if set(left.business_identifiers) & set(right.business_identifiers):
            score += 0.45
            reasons.append("stable business-document identifier agrees")
        else:
            conflicts.append("explicit business-document identifiers conflict")
    if left.dates_or_periods and right.dates_or_periods:
        if set(left.dates_or_periods) & set(right.dates_or_periods):
            score += 0.10
            reasons.append("date or period evidence agrees")
        else:
            conflicts.append("date or period evidence conflicts")
    if left.financial_controls and right.financial_controls:
        if left.financial_controls == right.financial_controls:
            score += 0.25
            reasons.append("financial controls agree")
        elif left.business_identifiers and right.business_identifiers and not conflicts:
            conflicts.append("financial controls conflict for the same identifier")
    if left.line_signature and right.line_signature:
        if left.line_signature == right.line_signature:
            score += 0.20
            reasons.append("normalized line-item composition agrees")
        else:
            reasons.append("line-item composition differs or is only partially comparable")
    if left.currencies and right.currencies and left.currencies != right.currencies:
        conflicts.append("explicit currencies conflict")
    elif left.currency_state == right.currency_state == "UNRESOLVED":
        reasons.append("shared unresolved currency does not establish identity")
    if conflicts:
        state = DocumentMatchState.CONFLICT
    elif score >= 0.80:
        state = DocumentMatchState.MATCHED
    elif score >= 0.65:
        state = DocumentMatchState.LIKELY_MATCH
    elif score >= 0.40:
        state = DocumentMatchState.POSSIBLE_MATCH
    else:
        state = DocumentMatchState.UNRESOLVED
    return DocumentMatchAssessment(
        left.representation.representation_id,
        right.representation.representation_id,
        state,
        round(score, 4),
        tuple(reasons),
        tuple(conflicts),
    )


def deduplicate_documents(candidates) -> DeduplicatedDocumentView:
    candidates = tuple(candidates)
    parents = list(range(len(candidates)))
    assessments = []

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            assessment = assess_document_match(left, candidates[right_index])
            assessments.append(assessment)
            if assessment.state in {DocumentMatchState.MATCHED, DocumentMatchState.LIKELY_MATCH}:
                left_root, right_root = find(left_index), find(right_index)
                if left_root != right_root:
                    parents[right_root] = left_root
    buckets = {}
    for index, candidate in enumerate(candidates):
        buckets.setdefault(find(index), []).append(candidate)
    groups = []
    for members in buckets.values():
        representation_ids = tuple(
            sorted(item.representation.representation_id for item in members)
        )
        relevant = tuple(
            item
            for item in assessments
            if item.left_representation_id in representation_ids
            and item.right_representation_id in representation_ids
        )
        preferred = sorted(
            members, key=lambda item: (-item.completeness, item.representation.representation_id)
        )[0]
        fingerprint = structural_fingerprint(
            IDENTITY_VERSION + ".business-document",
            tuple(sorted(item.candidate_fingerprint for item in members)),
        )
        state = DocumentMatchState.UNRESOLVED
        if len(members) > 1:
            state = (
                DocumentMatchState.MATCHED
                if relevant and all(item.state is DocumentMatchState.MATCHED for item in relevant)
                else DocumentMatchState.LIKELY_MATCH
            )
        groups.append(
            BusinessDocumentGroup(
                "business-document-" + fingerprint[:32],
                representation_ids,
                preferred.representation.representation_id,
                state,
                relevant,
            )
        )
    groups.sort(key=lambda item: item.business_document_fingerprint)
    return DeduplicatedDocumentView(tuple(groups), len(candidates), len(groups))


def _normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _identifier(value):
    normalized = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    return normalized if len(normalized) >= 5 else ""


def _description(value):
    tokens = re.findall(r"[a-z0-9]+", str(value or "").casefold())
    return " ".join(sorted(set(tokens)))


def _number(value):
    if value is None:
        return ""
    try:
        return format(Decimal(str(value).replace(",", "").replace("$", "")).normalize(), "f")
    except (InvalidOperation, ValueError):
        return str(value)
