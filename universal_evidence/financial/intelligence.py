from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation

from universal_evidence.domain import DomainClass, assess_domain
from universal_evidence.financial.models import (
    CanonicalFinancialObservation,
    CurrencyAuthority,
    CurrencyAuthorityType,
    FinancialAnalysis,
    FinancialConcept,
    ReconciliationEvidence,
    SemanticProposal,
)

_CURRENCY = re.compile(r"\b(USD|EUR|GBP|INR|JPY|AUD|CAD)\b", re.I)
_PERIODS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
    "september", "oct", "october", "nov", "november", "dec", "december",
    "month", "monthly", "fy", "fiscal", "year",
}


def _norm(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _decimal(value):
    try:
        text = str(value).replace(",", "").strip()
        negative = text.startswith("(") and text.endswith(")")
        text = re.sub(
            r"(?:USD|EUR|GBP|INR|JPY|AUD|CAD|[$€£₹¥])", "", text, flags=re.I
        )
        parsed = Decimal(text.strip("() "))
        return -parsed if negative else parsed
    except (InvalidOperation, AttributeError):
        return None


def _column(headers, terms):
    for index, header in enumerate(headers):
        if set(_norm(header).split()) & set(terms):
            return index
    return None


def _numeric_ratio(table, index):
    populated = [row[index] for row in table.rows if row[index] not in (None, "")]
    return (
        sum(_decimal(value) is not None for value in populated) / len(populated)
        if populated
        else 0
    )


def _ranked_column(table, terms):
    candidates = []
    for index, header in enumerate(table.headers):
        overlap = len(set(_norm(header).split()) & set(terms))
        if overlap:
            candidates.append((_numeric_ratio(table, index), overlap, -index, index))
    return max(candidates)[-1] if candidates else None


def _period_header(header):
    return bool(set(_norm(header).split()) & _PERIODS)


def _summary_rows(table, amount_indices):
    formulas = set(table.formula_cells)
    if not formulas or not amount_indices:
        return set()
    summary = set()
    for row_index in range(len(table.rows)):
        formula_ratio = sum((row_index, index) in formulas for index in amount_indices) / len(
            amount_indices
        )
        prior_formula_ratio = (
            sum(
                (prior, index) in formulas
                for prior in range(row_index)
                for index in amount_indices
            )
            / (row_index * len(amount_indices))
            if row_index
            else 1
        )
        if row_index and formula_ratio >= 0.8 and prior_formula_ratio <= 0.25:
            summary.add(row_index)
    return summary


def _currency_authority(table, currency_index, *, confirmed_currency=None):
    evidence = []
    values = set()
    authority = CurrencyAuthorityType.UNKNOWN
    if currency_index is not None:
        values = {str(row[currency_index]).upper() for row in table.rows if row[currency_index]}
        authority = CurrencyAuthorityType.ROW
        evidence.append(f"column:{table.headers[currency_index]}")
    else:
        for header in table.headers:
            values.update(item.upper() for item in _CURRENCY.findall(str(header)))
        if values:
            authority = CurrencyAuthorityType.HEADER_CONTEXT
            evidence.append("header-context")
        if not values:
            for _key, value in table.source_metadata:
                values.update(item.upper() for item in _CURRENCY.findall(str(value)))
            if values:
                authority = CurrencyAuthorityType.SOURCE_METADATA
                evidence.append("workbook-context")
    if confirmed_currency:
        values = {confirmed_currency.upper()}
        authority = CurrencyAuthorityType.HUMAN_CONFIRMED
        evidence.append("human-confirmation")
    conflicted = len(values) > 1
    if conflicted:
        authority = CurrencyAuthorityType.MIXED
    governed = bool(values) and not conflicted and authority in {
        CurrencyAuthorityType.ROW,
        CurrencyAuthorityType.HEADER_CONTEXT,
        CurrencyAuthorityType.SOURCE_METADATA,
        CurrencyAuthorityType.HUMAN_CONFIRMED,
    }
    fp = hashlib.sha256(
        repr((authority.value, sorted(values), evidence, table.scope_key)).encode()
    ).hexdigest()
    return CurrencyAuthority(
        authority,
        tuple(sorted(values)),
        "ROW" if authority is CurrencyAuthorityType.ROW else "DATASET",
        tuple(evidence),
        governed,
        conflicted,
        fp,
    )


def _reconciled_amount(table, quantity, unit, excluded):
    best = None
    for candidate in range(len(table.headers)):
        if candidate in excluded or _numeric_ratio(table, candidate) < 0.6:
            continue
        matched = compared = 0
        for row in table.rows:
            q, u, a = _decimal(row[quantity]), _decimal(row[unit]), _decimal(row[candidate])
            if None not in (q, u, a):
                compared += 1
                tolerance = max(Decimal("0.01"), abs(a) * Decimal("0.001"))
                matched += abs(q * u - a) <= tolerance
        score = matched / compared if compared else 0
        if best is None or score > best[0]:
            best = (score, candidate, matched, compared)
    return best


def analyze_financial_evidence(
    table, *, confirm_domain=False, confirm_measure=False, confirmed_currency=None
):
    domain = assess_domain(table, confirmed=confirm_domain)
    headers = table.headers
    quantity = _ranked_column(table, {"quantity", "qty", "units", "volume"})
    unit = _ranked_column(table, {"unit", "rate"})
    direct_amount = _ranked_column(
        table, {"amount", "cost", "charge", "extended", "extension", "total"}
    )
    if direct_amount is not None and _numeric_ratio(table, direct_amount) < 0.6:
        direct_amount = None
    currency_index = _column(headers, {"currency", "ccy"})
    service = _column(headers, {"service", "services", "offering", "product", "products"})
    region = _column(headers, {"region", "geo", "location"})
    proposals = []
    if quantity is not None:
        proposals.append(
            SemanticProposal(
                quantity, headers[quantity], FinancialConcept.QUANTITY, 0.72,
                ("DATATYPE", "DISTRIBUTION", "NEIGHBOR"), True, confirm_measure,
            )
        )
    if unit is not None:
        proposals.append(
            SemanticProposal(
                unit, headers[unit], FinancialConcept.UNIT_PRICE, 0.78,
                ("HEADER", "DATATYPE", "NEIGHBOR"), True, confirm_measure,
            )
        )

    reconciliation = None
    amount_indices = [direct_amount] if direct_amount is not None else []
    if quantity is not None and unit is not None:
        best = _reconciled_amount(table, quantity, unit, {quantity, unit})
        if best and best[0] >= 0.8:
            amount_indices = [best[1]]
            reconciliation = ReconciliationEvidence(
                "unit_price*quantity≈extended_amount", best[2], best[3], best[0],
                Decimal("0.001"), tuple(f"row:{index + 1}" for index in range(best[3])),
            )

    temporal_amounts = [
        index for index, header in enumerate(headers)
        if _period_header(header) and _numeric_ratio(table, index) >= 0.6
    ]
    if not amount_indices and len(temporal_amounts) >= 3:
        amount_indices = temporal_amounts
    summary_rows = _summary_rows(table, amount_indices)
    cached_cells = set(table.cached_formula_cells)
    for amount_index in amount_indices:
        signals = ["DATATYPE", "STRUCTURAL", "DOMAIN"]
        if reconciliation and amount_index == amount_indices[0]:
            signals.append("RECONCILIATION")
        if amount_index in temporal_amounts:
            signals.append("TEMPORAL_FINANCIAL_MATRIX")
        if any(column == amount_index for _row, column in cached_cells):
            signals.append("CACHED_FORMULA_VALUE")
        proposals.append(
            SemanticProposal(
                amount_index, headers[amount_index], FinancialConcept.EXTENDED_AMOUNT,
                0.92 if "RECONCILIATION" in signals else (
                    0.82 if "TEMPORAL_FINANCIAL_MATRIX" in signals else 0.68
                ),
                tuple(signals), not confirm_measure, confirm_measure,
            )
        )

    currency = _currency_authority(table, currency_index, confirmed_currency=confirmed_currency)
    blocked = []
    if domain.domain is not DomainClass.CLOUD_BILLING or (
        domain.confirmation_required and not confirm_domain
    ):
        blocked.append("governed cloud billing domain is required")
    if not amount_indices or not confirm_measure:
        blocked.append("governed additive monetary measure is required")
    if not currency.governed:
        blocked.append("single governed currency authority is required")

    observations = []
    if not blocked:
        for row_number, row in enumerate(table.rows, start=1):
            if row_number - 1 in summary_rows:
                continue
            for amount_index in amount_indices:
                value = _decimal(row[amount_index])
                if value is None:
                    continue
                dimensions = []
                if service is not None and row[service] not in (None, ""):
                    dimensions.append(("service", str(row[service])))
                elif amount_indices == temporal_amounts and row[0] not in (None, ""):
                    dimensions.append(("service", str(row[0])))
                if region is not None and row[region] not in (None, ""):
                    dimensions.append(("region", str(row[region])))
                if amount_index in temporal_amounts:
                    dimensions.append(("period", str(headers[amount_index])))
                identity = (
                    table.scope_key, table.source_id, table.sheet_id, row_number,
                    amount_index, value, currency.fingerprint, dimensions,
                )
                fp = hashlib.sha256(repr(identity).encode()).hexdigest()
                provenance = []
                if reconciliation:
                    provenance.append(reconciliation.relationship)
                if (row_number - 1, amount_index) in cached_cells:
                    provenance.append("cached-formula-value")
                observations.append(
                    CanonicalFinancialObservation(
                        "finobs-" + fp[:24], table.organization_id, table.tenant_id,
                        table.prospect_id, table.analysis_id, table.source_id, table.file_id,
                        table.sheet_id, row_number, headers[amount_index], domain.fingerprint,
                        f"confirmed:{FinancialConcept.EXTENDED_AMOUNT.value}",
                        "cmp-p1r-normalization-2", "ADDITIVE_EXTENDED_AMOUNT",
                        currency.fingerprint, "CLOUD_SPEND", value, currency.currencies[0],
                        tuple(dimensions), tuple(provenance), fp,
                    )
                )
    return FinancialAnalysis(
        domain, tuple(proposals), currency, reconciliation, tuple(observations),
        not blocked, tuple(blocked),
    )
