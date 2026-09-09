"""Governed candidate normalization for financial document evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

from universal_evidence.documents import SemanticDecisionState, structural_fingerprint
from universal_evidence.financial.models import (
    CurrencyAuthority,
    CurrencyAuthorityType,
    FinancialConcept,
)

FINANCIAL_DOCUMENT_VERSION = "pue-011f.financial-document.v1"


class ConceptRole(str, Enum):
    DETAIL = "DETAIL"
    CONTROL = "CONTROL"
    ADJUSTMENT = "ADJUSTMENT"
    DERIVED = "DERIVED"
    STATE = "STATE"
    CONTEXT = "CONTEXT"


class AggregationEligibility(str, Enum):
    ELIGIBLE_DETAIL = "ELIGIBLE_DETAIL"
    CONTROL_ONLY = "CONTROL_ONLY"
    ADJUSTMENT_ONLY = "ADJUSTMENT_ONLY"
    DERIVED_ONLY = "DERIVED_ONLY"
    STATE_ONLY = "STATE_ONLY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ReconciliationState(str, Enum):
    RECONCILED = "RECONCILED"
    MISMATCH = "MISMATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


_ROLE = {
    FinancialConcept.LINE_ITEM_QUANTITY: ConceptRole.DETAIL,
    FinancialConcept.LINE_ITEM_UNIT_PRICE: ConceptRole.DETAIL,
    FinancialConcept.LINE_ITEM_AMOUNT: ConceptRole.DETAIL,
    FinancialConcept.SUBTOTAL: ConceptRole.CONTROL,
    FinancialConcept.TOTAL_DUE: ConceptRole.CONTROL,
    FinancialConcept.TAX: ConceptRole.ADJUSTMENT,
    FinancialConcept.TAX_RATE: ConceptRole.CONTEXT,
    FinancialConcept.DISCOUNT: ConceptRole.ADJUSTMENT,
    FinancialConcept.CREDIT: ConceptRole.ADJUSTMENT,
    FinancialConcept.FEE: ConceptRole.ADJUSTMENT,
    FinancialConcept.MONTHLY_EQUIVALENT: ConceptRole.DERIVED,
    FinancialConcept.ANNUAL_AMOUNT: ConceptRole.DERIVED,
    FinancialConcept.BALANCE: ConceptRole.STATE,
    FinancialConcept.BILLING_PERIOD: ConceptRole.CONTEXT,
    FinancialConcept.INVOICE_DATE: ConceptRole.CONTEXT,
    FinancialConcept.DUE_DATE: ConceptRole.CONTEXT,
    FinancialConcept.CURRENCY: ConceptRole.CONTEXT,
}


@dataclass(frozen=True, slots=True)
class FinancialValueEvidence:
    region_id: str
    reference: str
    label: str
    value: object
    currency_candidate: str | None = None
    currency_source: str | None = None
    number_format: str | None = None
    formula: str | None = None
    cached_value_available: bool = False


@dataclass(frozen=True, slots=True)
class FinancialLineEvidence:
    region_id: str
    row_reference: str
    description_reference: str | None = None
    quantity: object | None = None
    unit_price: object | None = None
    amount: object | None = None
    currency_candidate: str | None = None
    formula_cells: tuple[str, ...] = ()
    cached_formula_cells: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FinancialConceptObservation:
    observation_id: str
    region_id: str
    reference: str
    concept: FinancialConcept
    role: ConceptRole
    source_value: object
    normalized_amount: Decimal | None
    signed_effect: Decimal | None
    aggregation_eligibility: AggregationEligibility
    financial_confidence: float
    semantic_confidence: float
    decision_state: SemanticDecisionState
    explanation: str
    formula_uncertain: bool
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ArithmeticReconciliation:
    relationship: str
    state: ReconciliationState
    expected: Decimal | None
    observed: Decimal | None
    difference: Decimal | None
    tolerance: Decimal
    references: tuple[str, ...]
    explanation: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class FinancialDocumentInput:
    evidence_set_id: str
    organization_id: str | None
    tenant_id: str | None
    prospect_id: str
    analysis_id: str
    semantic_confidence: float
    region_ids: tuple[str, ...]
    lines: tuple[FinancialLineEvidence, ...] = ()
    values: tuple[FinancialValueEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class FinancialDocumentAnalysis:
    evidence_set_id: str
    concept_observations: tuple[FinancialConceptObservation, ...]
    reconciliations: tuple[ArithmeticReconciliation, ...]
    currency: CurrencyAuthority
    eligible_detail_total: Decimal | None
    tax_total: Decimal | None
    gross_payable: Decimal | None
    aggregation_authorized: bool
    blocked_reasons: tuple[str, ...]
    fingerprint: str
    business_document_fingerprint: str | None = None


def normalize_financial_document(
    evidence: FinancialDocumentInput, *, tolerance: Decimal = Decimal("0.01")
) -> FinancialDocumentAnalysis:
    """Normalize document concepts without granting canonical P1 authority."""
    observations: list[FinancialConceptObservation] = []
    reconciliations: list[ArithmeticReconciliation] = []
    for line in evidence.lines:
        observations.extend(_line_observations(line, evidence.semantic_confidence))
        reconciliations.append(_line_reconciliation(line, tolerance))
    for value in evidence.values:
        concept = _concept_from_label(value.label)
        observations.append(
            _value_observation(value, concept, evidence.semantic_confidence)
        )
    currency = _currency_authority(evidence)
    detail = _amounts(observations, FinancialConcept.LINE_ITEM_AMOUNT)
    subtotal = _amounts(observations, FinancialConcept.SUBTOTAL)
    reconciliations.append(
        _reconcile(
            "LINE_ITEMS_TO_SUBTOTAL",
            sum(detail) if detail else None,
            subtotal[0] if len(subtotal) == 1 else None,
            tolerance,
            tuple(
                item.reference
                for item in observations
                if item.concept
                in {FinancialConcept.LINE_ITEM_AMOUNT, FinancialConcept.SUBTOTAL}
            ),
        )
    )
    total_due = _amounts(observations, FinancialConcept.TOTAL_DUE)
    taxes = _amounts(observations, FinancialConcept.TAX)
    fees = _amounts(observations, FinancialConcept.FEE)
    discounts = _effects(observations, FinancialConcept.DISCOUNT)
    credits = _effects(observations, FinancialConcept.CREDIT)
    base = subtotal[0] if len(subtotal) == 1 else (sum(detail) if detail else None)
    expected_due = (
        base + sum(taxes) + sum(fees) + sum(discounts) + sum(credits)
        if base is not None
        else None
    )
    reconciliations.append(
        _reconcile(
            "COMPONENTS_TO_TOTAL_DUE",
            expected_due,
            total_due[0] if len(total_due) == 1 else None,
            tolerance,
            tuple(
                item.reference
                for item in observations
                if item.role
                in {ConceptRole.DETAIL, ConceptRole.CONTROL, ConceptRole.ADJUSTMENT}
            ),
        )
    )
    blocked = []
    if not currency.governed or currency.conflicted:
        blocked.append("single governed currency authority is required")
    if any(item.formula_uncertain for item in observations):
        blocked.append("formula-derived value has unavailable or unverified cache")
    if any(item.state is ReconciliationState.MISMATCH for item in reconciliations):
        blocked.append("financial document reconciliation conflict")
    subtotal_result = reconciliations[-2]
    if subtotal and subtotal_result.state is ReconciliationState.MISMATCH:
        blocked.append("line items and subtotal conflict")
    eligible_total = sum(detail) if detail else None
    tax_total = sum(taxes) if taxes else None
    gross = total_due[0] if len(total_due) == 1 else expected_due
    identity = structural_fingerprint(
        FINANCIAL_DOCUMENT_VERSION,
        evidence.evidence_set_id,
        repr(tuple(observations)),
        repr(tuple(reconciliations)),
        currency.fingerprint,
        tuple(blocked),
    )
    return FinancialDocumentAnalysis(
        evidence.evidence_set_id,
        tuple(observations),
        tuple(reconciliations),
        currency,
        eligible_total,
        tax_total,
        gross,
        not blocked and eligible_total is not None,
        tuple(blocked),
        identity,
    )


def assert_financial_scope(left: FinancialDocumentInput, right: FinancialDocumentInput):
    if (left.organization_id, left.tenant_id, left.prospect_id) != (
        right.organization_id,
        right.tenant_id,
        right.prospect_id,
    ):
        raise PermissionError("cross-tenant financial reconciliation is forbidden")


def _line_observations(line, semantic_confidence):
    output = []
    for concept, value, suffix in (
        (FinancialConcept.LINE_ITEM_QUANTITY, line.quantity, "quantity"),
        (FinancialConcept.LINE_ITEM_UNIT_PRICE, line.unit_price, "unit-price"),
        (FinancialConcept.LINE_ITEM_AMOUNT, line.amount, "amount"),
    ):
        if value is None:
            continue
        amount = _decimal(value)
        eligibility = (
            AggregationEligibility.ELIGIBLE_DETAIL
            if concept is FinancialConcept.LINE_ITEM_AMOUNT and amount is not None
            else AggregationEligibility.CONTROL_ONLY
        )
        output.append(
            _observation(
                line.region_id,
                f"{line.row_reference}:{suffix}",
                concept,
                value,
                amount,
                amount,
                eligibility,
                0.8,
                semantic_confidence,
                "line-region column role supports document detail candidate",
                bool(line.formula_cells and not line.cached_formula_cells),
            )
        )
    return output


def _value_observation(value, concept, semantic_confidence):
    amount = (
        _decimal(value.value)
        if concept and _ROLE[concept] not in {ConceptRole.CONTEXT}
        else None
    )
    if concept is None:
        return _observation(
            value.region_id,
            value.reference,
            FinancialConcept.MONETARY_AMOUNT,
            value.value,
            _decimal(value.value),
            None,
            AggregationEligibility.UNKNOWN,
            0.2,
            semantic_confidence,
            "label does not safely distinguish a financial document concept",
            bool(value.formula and not value.cached_value_available),
            SemanticDecisionState.UNRESOLVED,
        )
    role = _ROLE[concept]
    eligibility = {
        ConceptRole.CONTROL: AggregationEligibility.CONTROL_ONLY,
        ConceptRole.ADJUSTMENT: AggregationEligibility.ADJUSTMENT_ONLY,
        ConceptRole.DERIVED: AggregationEligibility.DERIVED_ONLY,
        ConceptRole.STATE: AggregationEligibility.STATE_ONLY,
        ConceptRole.CONTEXT: AggregationEligibility.CONTROL_ONLY,
    }.get(role, AggregationEligibility.UNKNOWN)
    signed = amount
    if concept in {FinancialConcept.DISCOUNT, FinancialConcept.CREDIT} and amount is not None:
        signed = -abs(amount)
    return _observation(
        value.region_id,
        value.reference,
        concept,
        value.value,
        amount,
        signed,
        eligibility,
        0.75,
        semantic_confidence,
        f"bounded label and value shape suggest {concept.value}",
        bool(value.formula and not value.cached_value_available),
    )


def _observation(
    region_id,
    reference,
    concept,
    source_value,
    amount,
    signed,
    eligibility,
    financial_confidence,
    semantic_confidence,
    explanation,
    formula_uncertain,
    state=SemanticDecisionState.CANDIDATE,
):
    identity = structural_fingerprint(
        FINANCIAL_DOCUMENT_VERSION + ".observation",
        region_id,
        reference,
        concept,
        repr(source_value),
        str(amount) if amount is not None else None,
        str(signed) if signed is not None else None,
    )
    return FinancialConceptObservation(
        "financial-concept-" + identity[:24],
        region_id,
        reference,
        concept,
        _ROLE.get(concept, ConceptRole.CONTEXT),
        source_value,
        amount,
        signed,
        eligibility,
        financial_confidence,
        semantic_confidence,
        state,
        explanation,
        formula_uncertain,
        identity,
    )


def _line_reconciliation(line, tolerance):
    quantity, unit_price, amount = map(_decimal, (line.quantity, line.unit_price, line.amount))
    expected = quantity * unit_price if quantity is not None and unit_price is not None else None
    return _reconcile(
        "QUANTITY_X_UNIT_PRICE_TO_LINE_AMOUNT",
        expected,
        amount,
        tolerance,
        (line.row_reference,),
    )


def _reconcile(relationship, expected, observed, tolerance, references):
    if expected is None or observed is None:
        state = ReconciliationState.INSUFFICIENT_EVIDENCE
        difference = None
    else:
        difference = observed - expected
        state = (
            ReconciliationState.RECONCILED
            if abs(difference) <= tolerance
            else ReconciliationState.MISMATCH
        )
    explanation = (
        "values reconcile within decimal tolerance"
        if state is ReconciliationState.RECONCILED
        else "values conflict outside decimal tolerance"
        if state is ReconciliationState.MISMATCH
        else "required values are not all evidenced"
    )
    identity = structural_fingerprint(
        FINANCIAL_DOCUMENT_VERSION + ".reconciliation",
        relationship,
        str(expected) if expected is not None else None,
        str(observed) if observed is not None else None,
        str(tolerance),
        references,
    )
    return ArithmeticReconciliation(
        relationship,
        state,
        expected,
        observed,
        difference,
        tolerance,
        references,
        explanation,
        identity,
    )


def _concept_from_label(label):
    ordered_tokens = re.findall(r"[a-z0-9]+", str(label).casefold())
    tokens = set(ordered_tokens)
    compact = "".join(ordered_tokens)
    rules = (
        (FinancialConcept.SUBTOTAL, {"subtotal", "sub-total"}),
        (FinancialConcept.TOTAL_DUE, {"totaldue", "amountdue"}),
        (FinancialConcept.BALANCE, {"balance", "balance due", "remaining"}),
        (FinancialConcept.TAX_RATE, {"taxrate"}),
        (FinancialConcept.TAX, {"tax", "vat", "gst"}),
        (FinancialConcept.DISCOUNT, {"discount"}),
        (FinancialConcept.CREDIT, {"credit"}),
        (FinancialConcept.FEE, {"fee", "surcharge"}),
        (FinancialConcept.MONTHLY_EQUIVALENT, {"monthly", "month"}),
        (FinancialConcept.ANNUAL_AMOUNT, {"annual", "yearly"}),
        (FinancialConcept.BILLING_PERIOD, {"billingperiod", "serviceperiod"}),
        (FinancialConcept.INVOICE_DATE, {"invoicedate", "documentdate"}),
        (FinancialConcept.DUE_DATE, {"duedate"}),
        (FinancialConcept.CURRENCY, {"currency", "ccy"}),
    )
    normalized = " ".join(ordered_tokens)
    for concept, aliases in rules:
        matched = any(
            alias in tokens
            or alias.replace(" ", "") in compact
            or alias == normalized
            for alias in aliases
        )
        if matched:
            return concept
    return None


def _currency_authority(evidence):
    candidates = []
    sources = []
    for line in evidence.lines:
        if line.currency_candidate:
            candidates.append(line.currency_candidate.upper())
            sources.append("line")
    for value in evidence.values:
        if value.currency_candidate:
            candidates.append(value.currency_candidate.upper())
            sources.append(value.currency_source or "metadata")
        elif value.number_format:
            symbols = [symbol for symbol in ("$", "€", "£", "¥") if symbol in value.number_format]
            candidates.extend(symbols)
            sources.extend("number_format" for _symbol in symbols)
    iso = sorted({item for item in candidates if re.fullmatch(r"[A-Z]{3}", item)})
    ambiguous = any(item in {"$", "£", "¥", "€"} for item in candidates)
    conflicted = len(iso) > 1
    if conflicted:
        authority_type = CurrencyAuthorityType.MIXED
    elif len(iso) == 1 and "line" in sources:
        authority_type = CurrencyAuthorityType.ROW
    elif len(iso) == 1:
        authority_type = CurrencyAuthorityType.SOURCE_METADATA
    else:
        authority_type = CurrencyAuthorityType.UNKNOWN
    governed = len(iso) == 1 and not conflicted and not ambiguous
    identity = structural_fingerprint(
        FINANCIAL_DOCUMENT_VERSION + ".currency", authority_type, iso, sources, ambiguous
    )
    return CurrencyAuthority(
        authority_type,
        tuple(iso),
        evidence.evidence_set_id,
        tuple(sources),
        governed,
        conflicted or ambiguous,
        identity,
    )


def _decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9+-.]", "", value.replace(",", ""))
            return Decimal(cleaned) if cleaned else None
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _amounts(observations, concept):
    return [
        item.normalized_amount
        for item in observations
        if item.concept is concept and item.normalized_amount is not None
    ]


def _effects(observations, concept):
    return [
        item.signed_effect
        for item in observations
        if item.concept is concept and item.signed_effect is not None
    ]
