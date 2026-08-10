"""AWS classification evidence extraction without inventing unsupported values."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Mapping

from classification_engine.models import ClassificationEvidence

SOURCE_ORDER = (
    "cost_allocation_tags",
    "account_alias",
    "organizations_ou",
    "cost_categories",
    "historical_mapping",
    "resource_tags",
    "resource_names",
)

FIELD_ALIASES = {
    "accountname": "account_name",
    "businessunit": "business_unit",
    "bu": "business_unit",
    "department": "department",
    "costcenter": "cost_center",
    "environment": "environment",
    "env": "environment",
    "application": "application",
    "app": "application",
    "businessservice": "business_service",
    "owner": "owner",
    "userowner": "owner",
    "technicalowner": "technical_owner",
    "financeowner": "finance_owner",
    "criticality": "criticality",
    "userproduct": "application",
}

SOURCE_RELIABILITY = {
    "cost_allocation_tags": 0.90,
    "account_alias": 0.78,
    "organizations_ou": 0.88,
    "cost_categories": 0.90,
    "historical_mapping": 0.82,
    "resource_tags": 0.75,
    "resource_names": 0.55,
}


def collect_aws_evidence(
    *,
    organization_id: str,
    tenant_id: str,
    account_id: str,
    metadata: Mapping[str, Any],
    observed_at: datetime | None = None,
) -> tuple[ClassificationEvidence, ...]:
    timestamp = observed_at or datetime.now(timezone.utc)
    collected = []
    for source_type in SOURCE_ORDER:
        source = metadata.get(source_type)
        observations = _observations(source_type, source)
        for index, (field_name, value) in enumerate(observations):
            reference = f"aws:{account_id}:{source_type}:{field_name}:{index}"
            digest = hashlib.sha256(f"{reference}:{value}".encode()).hexdigest()
            collected.append(
                ClassificationEvidence(
                    evidence_id=digest,
                    organization_id=organization_id,
                    tenant_id=tenant_id,
                    source_type=source_type,
                    source_name="AWS",
                    source_reference=reference,
                    observed_field=field_name,
                    observed_value=value,
                    observed_at=timestamp,
                    source_reliability=SOURCE_RELIABILITY[source_type],
                    evidence_hash=digest,
                    metadata={"source_order": SOURCE_ORDER.index(source_type) + 1},
                )
            )
    return tuple(collected)


def _observations(source_type: str, source: Any) -> tuple[tuple[str, str], ...]:
    if isinstance(source, Mapping):
        return tuple(
            (field_name, str(value).strip())
            for key, value in sorted(source.items(), key=lambda item: str(item[0]).casefold())
            if (field_name := FIELD_ALIASES.get(_normalized_key(key))) and str(value).strip()
        )
    if not isinstance(source, str) or not source.strip():
        return ()
    value = source.strip()
    if source_type == "account_alias":
        observations = [("account_name", value)]
        tokens = [token for token in value.replace("_", "-").split("-") if token]
        environment = _environment(tokens)
        if environment:
            observations.append(("environment", environment))
        if len(tokens) >= 3:
            observations.append(("business_unit", tokens[-2].upper()))
        return tuple(observations)
    if source_type == "organizations_ou":
        return (("business_unit", value.rsplit("/", 1)[-1]),)
    if source_type == "cost_categories":
        return (("business_unit", value),)
    if source_type == "resource_names":
        token = value.replace("_", "-").split("-", 1)[0].strip()
        return (("application", token.upper()),) if token else ()
    return ()


def _normalized_key(value: Any) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _environment(tokens: list[str]) -> str | None:
    aliases = {
        "prod": "Production",
        "production": "Production",
        "nonprod": "NonProduction",
        "dev": "Development",
        "development": "Development",
        "test": "Test",
        "uat": "UAT",
        "sandbox": "Sandbox",
    }
    for token in reversed(tokens):
        if token.casefold() in aliases:
            return aliases[token.casefold()]
    return None
