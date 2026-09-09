"""Explainable semantic candidates over container-neutral evidence regions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from universal_evidence.documents import (
    EvidenceRegion,
    SemanticDecisionState,
    SemanticEvidenceSet,
    StructuralType,
    assert_same_scope,
    structural_fingerprint,
)
from universal_evidence.semantic.signals import normalize_text

SEMANTIC_CLASSIFIER_VERSION = "pue-011e.semantic.v1"


class SemanticRegionType(str, Enum):
    INVOICE_METADATA = "INVOICE_METADATA"
    INVOICE_LINE_ITEMS = "INVOICE_LINE_ITEMS"
    INVOICE_SUMMARY = "INVOICE_SUMMARY"
    LICENSE_ASSIGNMENT = "LICENSE_ASSIGNMENT"
    USAGE_DATA = "USAGE_DATA"
    ACCESS_ENTITLEMENT = "ACCESS_ENTITLEMENT"
    ASSET_INVENTORY = "ASSET_INVENTORY"
    OWNERSHIP_CONTEXT = "OWNERSHIP_CONTEXT"
    COST_CONTEXT = "COST_CONTEXT"
    GENERIC_TABULAR_EVIDENCE = "GENERIC_TABULAR_EVIDENCE"
    GENERIC_KEY_VALUE_EVIDENCE = "GENERIC_KEY_VALUE_EVIDENCE"
    GENERIC_TEXT_EVIDENCE = "GENERIC_TEXT_EVIDENCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class NormalizedRegionFeatures:
    region_id: str
    structural_type: StructuralType
    structural_confidence: float
    tokens: tuple[str, ...]
    labels: tuple[str, ...]
    primitive_types: tuple[str, ...]
    number_formats: tuple[str, ...]
    row_count: int | None
    column_count: int | None
    page_or_sheet_reference: str
    bounded_text_present: bool
    feature_fingerprint: str


@dataclass(frozen=True, slots=True)
class RegionSemanticCandidate:
    semantic_type: SemanticRegionType
    confidence: float
    supporting_reasons: tuple[str, ...]
    contradicting_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RegionSemanticClassification:
    region_id: str
    candidates: tuple[RegionSemanticCandidate, ...]
    decision_state: SemanticDecisionState
    semantic_confidence: float | None
    structural_confidence: float
    classifier_version: str
    explanation: str
    semantic_fingerprint: str


@dataclass(frozen=True, slots=True)
class EvidenceSetCandidate:
    evidence_set: SemanticEvidenceSet
    region_classification_ids: tuple[str, ...]
    grouping_confidence: float
    grouping_reasons: tuple[str, ...]


_GROUPS = {
    "document": {"invoice", "document", "statement", "bill"},
    "identifier": {"number", "no", "id", "reference"},
    "date": {"date", "dated", "period", "due"},
    "description": {"description", "item", "product", "service", "detail"},
    "quantity": {"quantity", "qty", "units", "hours", "count"},
    "unit_price": {"unitprice", "rate", "price", "unitcost"},
    "amount": {"amount", "charge", "extended", "lineamount", "cost"},
    "summary": {"subtotal", "tax", "total", "balance", "discount", "credit"},
    "currency": {"currency", "ccy"},
    "user": {"user", "email", "person", "assignee", "account"},
    "license": {"license", "licence", "subscription", "tier", "sku", "seat"},
    "assignment": {"assigned", "assignment", "status", "allocated"},
    "access": {"access", "role", "permission", "entitlement", "group", "console"},
    "usage": {"usage", "consumption", "activity", "metric", "utilization"},
    "resource": {"resource", "meter", "device", "instance"},
    "asset": {"asset", "application", "software", "technology"},
    "inventory": {"version", "lifecycle", "serial", "inventory", "type"},
    "organization": {"department", "team", "businessunit", "costcenter"},
    "ownership": {"owner", "ownership", "responsible", "manager"},
}


def normalize_region_features(
    region: EvidenceRegion, profile: Any, contextual_labels: tuple[str, ...] = ()
) -> NormalizedRegionFeatures:
    """Adapt XLSX or PDF structural profiles to one bounded feature contract."""
    labels = tuple(str(value)[:80] for value in getattr(profile, "bounded_labels", ()))
    if not labels:
        labels = tuple(str(value)[:80] for value in getattr(profile, "candidate_headers", ()))
    excerpt = str(getattr(profile, "bounded_excerpt", "") or "")[:160]
    combined = " ".join((*labels, *contextual_labels, excerpt))
    tokens = tuple(sorted(set(_semantic_tokens(combined))))
    distribution = getattr(profile, "primitive_distribution", ())
    primitive_types = tuple(sorted(str(key) for key, count in distribution if count))
    formats = tuple(str(value)[:128] for value in getattr(profile, "number_formats", ()))
    row_count = getattr(profile, "row_count", None)
    column_count = getattr(profile, "column_count", None)
    if row_count is None and hasattr(region.location, "start_row"):
        row_count = region.location.end_row - region.location.start_row + 1
    if column_count is None and hasattr(region.location, "start_column"):
        column_count = region.location.end_column - region.location.start_column + 1
    location_reference = (
        getattr(region.location, "page_id", None)
        or getattr(region.location, "sheet_id", None)
        or "delimited"
    )
    identity = structural_fingerprint(
        SEMANTIC_CLASSIFIER_VERSION + ".features",
        region.region_id,
        region.structural_type,
        tokens,
        labels,
        primitive_types,
        formats,
        row_count,
        column_count,
    )
    return NormalizedRegionFeatures(
        region.region_id,
        region.structural_type,
        region.structural_confidence,
        tokens,
        labels,
        primitive_types,
        formats,
        row_count,
        column_count,
        str(location_reference),
        bool(excerpt),
        identity,
    )


def classify_region(features: NormalizedRegionFeatures) -> RegionSemanticClassification:
    groups = {name for name, vocabulary in _GROUPS.items() if set(features.tokens) & vocabulary}
    candidates: list[RegionSemanticCandidate] = []
    _candidate_invoice(features, groups, candidates)
    _candidate_assignments(features, groups, candidates)
    _candidate_usage_inventory(features, groups, candidates)
    _candidate_context(features, groups, candidates)
    generic = _generic_candidate(features)
    if generic:
        candidates.append(generic)
    candidates = sorted(candidates, key=lambda item: (-item.confidence, item.semantic_type.value))
    meaningful = [
        item for item in candidates if not item.semantic_type.value.startswith("GENERIC_")
    ]
    decision = SemanticDecisionState.CANDIDATE if meaningful else SemanticDecisionState.UNRESOLVED
    confidence = candidates[0].confidence if candidates else None
    explanation = (
        "; ".join(candidates[0].supporting_reasons)
        if candidates
        else "insufficient bounded semantic evidence"
    )
    identity = structural_fingerprint(
        SEMANTIC_CLASSIFIER_VERSION + ".classification",
        features.feature_fingerprint,
        tuple(candidates),
        decision,
    )
    return RegionSemanticClassification(
        features.region_id,
        tuple(candidates),
        decision,
        confidence,
        features.structural_confidence,
        SEMANTIC_CLASSIFIER_VERSION,
        explanation,
        identity,
    )


def classify_decomposition(decomposition):
    profiles = dict(decomposition.region_profiles)
    partition_labels = {
        getattr(item, "sheet_id", ""): (str(getattr(item, "name", ""))[:80],)
        for item in getattr(decomposition, "sheets", ())
    }
    return tuple(
        classify_region(
            normalize_region_features(
                region,
                profiles[region.region_id],
                partition_labels.get(getattr(region.location, "sheet_id", ""), ()),
            )
        )
        for region in decomposition.regions
    )


def group_evidence_sets(regions, classifications) -> tuple[EvidenceSetCandidate, ...]:
    """Create deterministic, conservative candidates; never business-document identity."""
    if not regions:
        return ()
    classification_by_id = {item.region_id: item for item in classifications}
    first_context = regions[0].context
    for region in regions[1:]:
        assert_same_scope(first_context, region.context)
    ordered = sorted(regions, key=_region_order)
    invoice_partitions = {
        _physical_partition(region)
        for region in ordered
        if _leading_type(classification_by_id[region.region_id])
        is SemanticRegionType.INVOICE_LINE_ITEMS
    }
    consumed: set[str] = set()
    output: list[EvidenceSetCandidate] = []
    for index, region in enumerate(ordered):
        if region.region_id in consumed:
            continue
        classification = classification_by_id[region.region_id]
        leading = _leading_type(classification)
        if (
            leading
            in {
                SemanticRegionType.GENERIC_TEXT_EVIDENCE,
                SemanticRegionType.GENERIC_KEY_VALUE_EVIDENCE,
                SemanticRegionType.UNKNOWN,
            }
            and _physical_partition(region) in invoice_partitions
            and any(
                _same_physical_partition(region, later)
                and _leading_type(classification_by_id[later.region_id])
                is SemanticRegionType.INVOICE_LINE_ITEMS
                for later in ordered[index + 1 :]
            )
        ):
            continue
        members = [region]
        reasons = ["region has a compatible ranked semantic candidate"]
        set_type = leading
        if leading in {
            SemanticRegionType.INVOICE_METADATA,
            SemanticRegionType.INVOICE_LINE_ITEMS,
            SemanticRegionType.INVOICE_SUMMARY,
        }:
            set_type = SemanticRegionType.INVOICE_METADATA
            candidates_to_consider = (
                ordered
                if leading is SemanticRegionType.INVOICE_LINE_ITEMS
                else ordered[index + 1 :]
            )
            for candidate in candidates_to_consider:
                if candidate.region_id == region.region_id:
                    continue
                if candidate.region_id in consumed or not _same_physical_partition(
                    region, candidate
                ):
                    continue
                candidate_type = _leading_type(classification_by_id[candidate.region_id])
                member_types = {
                    _leading_type(classification_by_id[item.region_id]) for item in members
                }
                if (
                    candidate_type
                    in {
                        SemanticRegionType.INVOICE_METADATA,
                        SemanticRegionType.INVOICE_LINE_ITEMS,
                        SemanticRegionType.INVOICE_SUMMARY,
                    }
                    and candidate_type not in member_types
                ):
                    members.append(candidate)
                    reasons.append("complementary invoice-related region candidate")
                    if candidate_type is SemanticRegionType.INVOICE_SUMMARY:
                        break
                elif members and candidate_type not in {
                    SemanticRegionType.GENERIC_TEXT_EVIDENCE,
                    SemanticRegionType.GENERIC_KEY_VALUE_EVIDENCE,
                    SemanticRegionType.UNKNOWN,
                }:
                    break
                elif _physical_partition(region) in invoice_partitions:
                    members.append(candidate)
                    reasons.append("bounded region shares an invoice-bearing physical partition")
        consumed.update(item.region_id for item in members)
        member_classifications = tuple(
            classification_by_id[item.region_id].semantic_fingerprint for item in members
        )
        semantic_type = set_type.value if set_type else SemanticRegionType.UNKNOWN.value
        fingerprint = structural_fingerprint(
            SEMANTIC_CLASSIFIER_VERSION + ".evidence-set",
            tuple(item.region_id for item in members),
            member_classifications,
            semantic_type,
        )
        confidence = min(
            classification_by_id[item.region_id].semantic_confidence or 0.0 for item in members
        )
        state = (
            SemanticDecisionState.CANDIDATE
            if set_type
            and set_type is not SemanticRegionType.UNKNOWN
            and not set_type.value.startswith("GENERIC_")
            else SemanticDecisionState.UNRESOLVED
        )
        evidence_set = SemanticEvidenceSet(
            "semantic-set-" + fingerprint[:24],
            first_context,
            tuple(item.region_id for item in members),
            semantic_type,
            state,
            confidence,
            tuple(item.lineage.physical_locator for item in members),
            semantic_fingerprint=fingerprint,
        )
        output.append(
            EvidenceSetCandidate(
                evidence_set,
                member_classifications,
                confidence,
                tuple(reasons),
            )
        )
    return tuple(output)


def _candidate_invoice(features, groups, candidates):
    if features.structural_type in {StructuralType.KEY_VALUE, StructuralType.FORM}:
        matched = groups & {"document", "identifier", "date", "currency"}
        if "document" in matched and len(matched) >= 3:
            candidates.append(
                _candidate(
                    SemanticRegionType.INVOICE_METADATA,
                    0.78,
                    "document, identifier, and date/currency label combination",
                )
            )
    if features.structural_type is StructuralType.TABULAR:
        required = {"description", "quantity", "unit_price", "amount"}
        if len(groups & required) >= 3 and "amount" in groups and "unit_price" in groups:
            candidates.append(
                _candidate(
                    SemanticRegionType.INVOICE_LINE_ITEMS,
                    0.82,
                    "description/quantity, unit-price, and amount-like columns coexist",
                )
            )
    if features.structural_type in {StructuralType.SUMMARY, StructuralType.KEY_VALUE}:
        if "summary" in groups and len(set(features.tokens) & _GROUPS["summary"]) >= 2:
            candidates.append(
                _candidate(
                    SemanticRegionType.INVOICE_SUMMARY,
                    0.76,
                    "multiple summary-control label candidates coexist",
                )
            )


def _candidate_assignments(features, groups, candidates):
    if features.structural_type is not StructuralType.TABULAR:
        return
    access_dominant = bool(
        set(features.tokens) & {"access", "console", "permission", "group", "iam", "portal"}
    ) and not bool(set(features.tokens) & {"seat", "subscription", "plan", "tier", "sku"})
    if {"user", "license", "assignment"}.issubset(groups):
        candidates.append(
            _candidate(
                SemanticRegionType.LICENSE_ASSIGNMENT,
                0.72 if access_dominant else 0.82,
                "license evidence coexists with user and assignment-state columns"
                + (" but access/role evidence dominates" if access_dominant else ""),
            )
        )
    if {"user", "access"}.issubset(groups):
        candidates.append(
            _candidate(
                SemanticRegionType.ACCESS_ENTITLEMENT,
                0.86 if access_dominant else 0.8,
                "user/account and role/permission/access columns coexist",
            )
        )


def _candidate_usage_inventory(features, groups, candidates):
    if features.structural_type is not StructuralType.TABULAR:
        return
    if "usage" in groups and ("resource" in groups or "quantity" in groups or "date" in groups):
        candidates.append(
            _candidate(
                SemanticRegionType.USAGE_DATA,
                0.78,
                "usage/metric evidence coexists with resource, quantity, or period columns",
            )
        )
    if {"asset", "inventory"}.issubset(groups):
        candidates.append(
            _candidate(
                SemanticRegionType.ASSET_INVENTORY,
                0.76,
                "asset/application and inventory-lifecycle columns coexist",
            )
        )


def _candidate_context(features, groups, candidates):
    if "organization" in groups and "ownership" in groups:
        candidates.append(
            _candidate(
                SemanticRegionType.OWNERSHIP_CONTEXT,
                0.68,
                "organization and owner-like labels provide context evidence only",
            )
        )
    if "organization" in groups and ("amount" in groups or "currency" in groups):
        candidates.append(
            _candidate(
                SemanticRegionType.COST_CONTEXT,
                0.65,
                "organization and cost/currency-like labels coexist",
            )
        )


def _generic_candidate(features):
    mapping = {
        StructuralType.TABULAR: SemanticRegionType.GENERIC_TABULAR_EVIDENCE,
        StructuralType.KEY_VALUE: SemanticRegionType.GENERIC_KEY_VALUE_EVIDENCE,
        StructuralType.SUMMARY: SemanticRegionType.GENERIC_KEY_VALUE_EVIDENCE,
        StructuralType.TEXT: SemanticRegionType.GENERIC_TEXT_EVIDENCE,
    }
    semantic_type = mapping.get(features.structural_type)
    if not semantic_type:
        return None
    return _candidate(
        semantic_type,
        0.4,
        "structural shape is known but specific semantic evidence is insufficient",
    )


def _candidate(semantic_type, score, reason):
    return RegionSemanticCandidate(semantic_type, score, (reason,))


def _semantic_tokens(value):
    normalized = normalize_text(value)
    tokens = set(normalized.split())
    compact = {re.sub(r"[^a-z0-9]", "", token) for token in tokens}
    for left, right in zip(normalized.split(), normalized.split()[1:]):
        compact.add(left + right)
    return tokens | compact


def _leading_type(classification):
    meaningful = [
        item.semantic_type
        for item in classification.candidates
        if not item.semantic_type.value.startswith("GENERIC_")
    ]
    if meaningful:
        return meaningful[0]
    if classification.candidates:
        return classification.candidates[0].semantic_type
    return SemanticRegionType.UNKNOWN


def _region_order(region):
    location = region.location
    partition = getattr(location, "sheet_id", None) or getattr(location, "page_id", None) or ""
    first = getattr(location, "start_row", None)
    if first is None:
        box = getattr(location, "bounding_box", None)
        first = box[1] if box else 0
    second = getattr(location, "start_column", None)
    if second is None:
        box = getattr(location, "bounding_box", None)
        second = box[0] if box else 0
    return partition, first, second, region.region_id


def _same_physical_partition(left, right):
    left_location = left.location
    right_location = right.location
    left_sheet = getattr(left_location, "sheet_id", None)
    right_sheet = getattr(right_location, "sheet_id", None)
    if left_sheet or right_sheet:
        return left_sheet == right_sheet
    left_page = getattr(left_location, "page_number", None)
    right_page = getattr(right_location, "page_number", None)
    return left_page is not None and right_page is not None and abs(left_page - right_page) <= 1


def _physical_partition(region):
    location = region.location
    return (
        getattr(location, "sheet_id", None)
        or getattr(location, "page_id", None)
        or region.container_id
    )
