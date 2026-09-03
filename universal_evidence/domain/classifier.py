from __future__ import annotations

import hashlib
import re

from universal_evidence.domain.models import (
    DomainAssessment,
    DomainClass,
    DomainConfidence,
    DomainGovernanceState,
    DomainSignal,
    ProviderClass,
)

CLASSIFIER_VERSION = "cmp-p1r-domain-2"
POLICY_VERSION = "cmp-p1r-domain-policy-2"

_PERIODS = {
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "sept",
    "september", "oct", "october", "nov", "november", "dec", "december",
    "month", "monthly", "fy", "fiscal", "year",
}


def _tokens(values) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", " ".join(str(v) for v in values).casefold()))


def assess_domain(table, *, confirmed: bool = False) -> DomainAssessment:
    """Assess a provider-neutral tabular evidence domain from multiple signals."""
    headers = tuple(str(value) for value in table.headers)
    samples = tuple(str(value) for row in table.rows[:20] for value in row if value is not None)
    metadata = tuple(value for _key, value in table.source_metadata)
    tokens = _tokens((*headers, table.sheet_name, *metadata, *samples))
    signals: list[DomainSignal] = []
    conflicts: list[DomainSignal] = []

    billing = tokens & {
        "cost",
        "price",
        "charge",
        "billing",
        "amount",
        "usage",
        "currency",
        "rate",
        "extension",
        "units",
        "settlement",
        "spend",
        "spending",
        "expense",
        "expenses",
        "expenditure",
        "invoice",
        "invoiced",
        "bill",
        "billed",
    }
    cloud = tokens & {
        "service",
        "region",
        "resource",
        "cloud",
        "meter",
        "subscription",
        "offering",
        "geo",
        "platform",
    }
    license_terms = tokens & {"license", "seat", "seats", "renewal", "subscription", "user"}
    inventory = tokens & {"asset", "application", "technology", "lifecycle", "owner", "version"}
    period_columns = sum(bool(_tokens((header,)) & _PERIODS) for header in headers)
    numeric_period_columns = sum(
        1
        for index, header in enumerate(headers)
        if _tokens((header,)) & _PERIODS
        and sum(
            isinstance(row[index], (int, float)) and not isinstance(row[index], bool)
            for row in table.rows
        )
        >= max(2, len(table.rows) // 2)
    )
    categorical_axis = any(
        sum(isinstance(row[index], str) and bool(row[index].strip()) for row in table.rows)
        >= max(2, len(table.rows) // 2)
        for index in range(len(headers))
    )
    if billing:
        signals.append(
            DomainSignal(
                "BILLING_FIELD_COMBINATION", "multiple financial/usage fields", 0.45, headers
            )
        )
    temporal_billing = bool(billing) and period_columns >= 3 and numeric_period_columns >= 3
    if temporal_billing and categorical_axis:
        signals.append(
            DomainSignal(
                "TEMPORAL_FINANCIAL_MATRIX",
                "categorical rows with repeated numeric financial periods",
                0.35,
                headers,
            )
        )
    if len(cloud) >= 2:
        signals.append(
            DomainSignal("CLOUD_DIMENSION_COMBINATION", "multiple cloud dimensions", 0.35, headers)
        )
    if len(license_terms) >= 3:
        signals.append(
            DomainSignal(
                "SAAS_LICENSE_COMBINATION", "license, seat, or renewal evidence", 0.65, headers
            )
        )
    if len(inventory) >= 3 and not billing:
        signals.append(
            DomainSignal(
                "INVENTORY_COMBINATION",
                "inventory fields without financial measures",
                0.65,
                headers,
            )
        )

    if billing and (len(cloud) >= 2 or temporal_billing):
        domain = DomainClass.CLOUD_BILLING
    elif len(license_terms) >= 3:
        domain = DomainClass.SAAS_LICENSING
    elif len(inventory) >= 3 and not billing:
        domain = DomainClass.TECHNOLOGY_INVENTORY
    else:
        domain = DomainClass.UNKNOWN

    provider_hits = {
        ProviderClass.AWS: tokens & {"aws", "amazon", "ec2", "s3"},
        ProviderClass.AZURE: tokens & {"azure", "microsoft", "meter"},
        ProviderClass.GCP: tokens & {"gcp", "google", "bigquery"},
    }
    supported = [provider for provider, hits in provider_hits.items() if hits]
    provider = supported[0] if len(supported) == 1 else ProviderClass.UNKNOWN
    if provider is not ProviderClass.UNKNOWN:
        signals.append(DomainSignal("PROVIDER_VALUE", "provider-specific evidence observed", 0.20))
    elif len(supported) > 1:
        conflicts.append(DomainSignal("PROVIDER_CONFLICT", "multiple providers observed", -0.30))

    score = min(
        1.0,
        sum(item.contribution for item in signals) + sum(item.contribution for item in conflicts),
    )
    if domain is DomainClass.UNKNOWN:
        confidence = DomainConfidence.INSUFFICIENT
    elif score >= 0.75:
        confidence = DomainConfidence.HIGH
    elif score >= 0.55:
        confidence = DomainConfidence.MEDIUM
    else:
        confidence = DomainConfidence.LOW
    confirmation = (
        domain is DomainClass.UNKNOWN or confidence is not DomainConfidence.HIGH or bool(conflicts)
    )
    state = (
        DomainGovernanceState.CONFIRMED
        if confirmed and domain is not DomainClass.UNKNOWN
        else (
            DomainGovernanceState.UNKNOWN
            if domain is DomainClass.UNKNOWN
            else DomainGovernanceState.PROPOSED
        )
    )
    identity = repr((domain.value, provider.value, score, signals, conflicts, table.scope_key))
    return DomainAssessment(
        domain,
        provider,
        round(score, 6),
        confidence,
        tuple(signals),
        tuple(conflicts),
        "; ".join(item.detail for item in signals) or "insufficient domain evidence",
        CLASSIFIER_VERSION,
        POLICY_VERSION,
        state,
        confirmation and not confirmed,
        hashlib.sha256(identity.encode()).hexdigest(),
    )
