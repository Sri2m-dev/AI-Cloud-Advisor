from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from data_fabric.source_facts.models import FactType, Freshness, SourceFactInput
from enterprise_registry.source_fact_projection import (
    EntityProjectionCandidate,
    EntityProjectionRule,
)


@dataclass(frozen=True, slots=True)
class AzureSourceFactMapping:
    source_fact: SourceFactInput
    projection_rule_id: str


_RESOURCE_RULES = {
    "Azure Subscription": EntityProjectionRule(
        "azure.subscription.identity.v1", "1", "azure", FactType.RESOURCE_IDENTITY,
        "resource_identity", "cloud_subscription", "resource_id", "name",
        ("provider", "resource_type", "subscription_id", "region"),
    ),
    "Azure Resource Group": EntityProjectionRule(
        "azure.resource_group.identity.v1", "1", "azure", FactType.RESOURCE_IDENTITY,
        "resource_identity", "cloud_resource", "resource_id", "name",
        ("provider", "resource_type", "subscription_id", "region", "resource_group"),
    ),
    "Azure VM": EntityProjectionRule(
        "azure.vm.identity.v1", "1", "azure", FactType.RESOURCE_IDENTITY,
        "resource_identity", "compute_resource", "resource_id", "name",
        ("provider", "resource_type", "subscription_id", "region", "resource_group", "status"),
    ),
    "Azure Storage Account": EntityProjectionRule(
        "azure.storage.identity.v1", "1", "azure", FactType.RESOURCE_IDENTITY,
        "resource_identity", "storage", "resource_id", "name",
        ("provider", "resource_type", "subscription_id", "region", "resource_group", "status"),
    ),
    "Azure VNet": EntityProjectionRule(
        "azure.vnet.identity.v1", "1", "azure", FactType.RESOURCE_IDENTITY,
        "resource_identity", "network", "resource_id", "name",
        ("provider", "resource_type", "subscription_id", "region", "resource_group", "status"),
    ),
}


class AzureSourceFactMapper:
    """Map only the live-validated Azure account and resource shapes to facts."""

    supported_resource_types = frozenset(_RESOURCE_RULES)

    def map_resources(
        self,
        accounts: Sequence[Mapping[str, Any]],
        resources: Sequence[Mapping[str, Any]],
    ) -> tuple[AzureSourceFactMapping, ...]:
        mapped = []
        for account in accounts:
            subscription_id = str(account.get("account_id") or "").strip()
            if not subscription_id or str(account.get("cloud") or "").lower() != "azure":
                continue
            resource_id = f"/subscriptions/{subscription_id}"
            mapped.append(
                self._mapping(
                    resource_id=resource_id,
                    resource_type="Azure Subscription",
                    name=str(account.get("account_name") or subscription_id),
                    subscription_id=subscription_id,
                    region=str(account.get("region") or "global"),
                    resource_group="",
                    status=str(account.get("status") or "ACTIVE"),
                )
            )

        for resource in resources:
            resource_type = str(resource.get("resource_type") or "")
            if resource_type not in self.supported_resource_types:
                continue
            resource_id = str(resource.get("resource_id") or resource.get("asset_id") or "").strip()
            subscription_id = str(resource.get("subscription_id") or "").strip()
            name = str(resource.get("name") or resource.get("asset_name") or "").strip()
            if (
                not resource_id
                or not subscription_id
                or not name
                or str(resource.get("provider") or "").lower() != "azure"
            ):
                continue
            mapped.append(
                self._mapping(
                    resource_id=resource_id,
                    resource_type=resource_type,
                    name=name,
                    subscription_id=subscription_id,
                    region=str(resource.get("region") or "global"),
                    resource_group=str(resource.get("resource_group") or ""),
                    status=str(resource.get("status") or "UNKNOWN"),
                )
            )
        return tuple(mapped)

    @staticmethod
    def projection_candidate(fact) -> EntityProjectionCandidate:
        resource_type = str((fact.value or {}).get("resource_type") or "")
        rule = _RESOURCE_RULES.get(resource_type)
        if rule is None:
            raise ValueError("Azure SourceFact has no approved canonical projection rule")
        return EntityProjectionCandidate(fact, rule.rule_id)

    @staticmethod
    def projection_rules() -> dict[str, EntityProjectionRule]:
        return {rule.rule_id: rule for rule in _RESOURCE_RULES.values()}

    @staticmethod
    def map_relationships(_resources) -> tuple[()]:
        return ()

    @staticmethod
    def _mapping(
        *,
        resource_id: str,
        resource_type: str,
        name: str,
        subscription_id: str,
        region: str,
        resource_group: str,
        status: str,
    ) -> AzureSourceFactMapping:
        rule = _RESOURCE_RULES[resource_type]
        value = {
            "provider": "Azure",
            "resource_id": resource_id,
            "resource_type": resource_type,
            "subscription_id": subscription_id,
            "region": region,
            "resource_group": resource_group,
            "name": name,
            "status": status,
        }
        return AzureSourceFactMapping(
            SourceFactInput(
                source_record_id=resource_id,
                fact_type=FactType.RESOURCE_IDENTITY,
                subject_reference=resource_id,
                predicate="resource_identity",
                value=value,
                freshness=Freshness.FRESH,
                evidence_reference=f"azure:{subscription_id}:{resource_id}",
                provenance={
                    "provider": "Azure",
                    "resource_id": resource_id,
                    "subscription_id": subscription_id,
                    "resource_type": resource_type,
                },
            ),
            rule.rule_id,
        )
