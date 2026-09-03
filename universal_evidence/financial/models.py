from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class FinancialConcept(str, Enum):
    MONETARY_AMOUNT = "financial.monetary_amount"
    COST = "financial.cost.total"
    CHARGE = "financial.charge"
    UNIT_PRICE = "financial.cost.unit"
    EXTENDED_AMOUNT = "financial.extended_amount"
    QUANTITY = "financial.quantity"
    DISCOUNT = "financial.discount"
    CREDIT = "financial.credit"
    TAX = "financial.tax"
    SAVINGS = "financial.savings"
    CURRENCY = "financial.currency"


class CurrencyAuthorityType(str, Enum):
    ROW = "ROW"
    DATASET = "DATASET"
    HEADER_CONTEXT = "HEADER_CONTEXT"
    SOURCE_METADATA = "SOURCE_METADATA"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EvidenceTable:
    organization_id: str
    tenant_id: str
    prospect_id: str
    analysis_id: str
    source_id: str
    file_id: str
    sheet_id: str
    sheet_name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    source_metadata: tuple[tuple[str, str], ...] = ()
    formula_cells: tuple[tuple[int, int], ...] = ()
    cached_formula_cells: tuple[tuple[int, int], ...] = ()

    @property
    def scope_key(self):
        return (self.organization_id, self.tenant_id, self.prospect_id, self.analysis_id)


@dataclass(frozen=True, slots=True)
class SemanticProposal:
    column_index: int
    header: str
    concept: FinancialConcept
    score: float
    signals: tuple[str, ...]
    confirmation_required: bool
    governed: bool


@dataclass(frozen=True, slots=True)
class CurrencyAuthority:
    authority_type: CurrencyAuthorityType
    currencies: tuple[str, ...]
    scope: str
    evidence: tuple[str, ...]
    governed: bool
    conflicted: bool
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ReconciliationEvidence:
    relationship: str
    matched_rows: int
    compared_rows: int
    ratio: float
    tolerance: Decimal
    references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanonicalFinancialObservation:
    observation_id: str
    organization_id: str
    tenant_id: str
    prospect_id: str
    analysis_id: str
    source_id: str
    file_id: str
    sheet_id: str
    row_number: int
    field: str
    domain_decision: str
    semantic_decision: str
    normalization_run_id: str
    measure_authority: str
    currency_authority: str
    financial_classification: str
    amount: Decimal
    currency: str
    dimensions: tuple[tuple[str, str], ...]
    reconciliation_evidence: tuple[str, ...]
    publication_fingerprint: str
    version: int = 1


@dataclass(frozen=True, slots=True)
class FinancialAnalysis:
    domain: object
    proposals: tuple[SemanticProposal, ...]
    currency: CurrencyAuthority
    reconciliation: ReconciliationEvidence | None
    observations: tuple[CanonicalFinancialObservation, ...]
    authorized: bool
    blocked_reasons: tuple[str, ...]
