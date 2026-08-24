"""Thin adapters from authoritative domain rows to P3 EnterpriseEntity contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from data_fabric.contracts import EnterpriseEntity, EntityType
from data_fabric.foundation import TenantContext
from enterprise_registry.canonical import enterprise_entity_from_source


class DomainEnterpriseAdapter:
    entity_type: EntityType
    source_system: str
    id_fields: tuple[str, ...]
    name_fields: tuple[str, ...]

    @staticmethod
    def _value(row: Mapping[str, Any], fields: tuple[str, ...]) -> str:
        for field in fields:
            value = str(row.get(field) or "").strip()
            if value:
                return value
        return ""

    def adapt(self, context: TenantContext, row: Mapping[str, Any]) -> EnterpriseEntity:
        source_id = self._value(row, self.id_fields)
        name = self._value(row, self.name_fields) or source_id
        if not source_id:
            raise ValueError(f"{self.entity_type.value} source identity is required")
        aliases = tuple(
            str(value).strip() for value in (row.get("aliases") or ()) if str(value).strip()
        )
        search = {
            key: row.get(key)
            for key in (
                "owner",
                "business_unit",
                "department",
                "application",
                "business_service",
                "technology",
                "account_id",
                "vendor",
                "cost_center",
            )
            if row.get(key) not in (None, "")
        }
        confidence = row.get("confidence")
        if confidence is None:
            confidence = row.get("confidence_score")
        if confidence is None:
            confidence = 1.0
        return enterprise_entity_from_source(
            context=context,
            entity_type=self.entity_type,
            source_system=str(row.get("source_system") or self.source_system),
            source_entity_id=source_id,
            canonical_name=name,
            display_name=str(row.get("display_name") or name),
            aliases=aliases,
            lifecycle_status=str(row.get("lifecycle_status") or row.get("status") or "active"),
            classification_status=str(row.get("classification_status") or "unclassified"),
            confidence=float(confidence),
            owner_reference=str(row.get("owner_id") or row.get("owner") or "") or None,
            business_context_reference=str(
                row.get("business_context_reference") or row.get("business_unit") or ""
            )
            or None,
            financial_context_reference=str(
                row.get("financial_context_reference") or row.get("cost_center") or ""
            )
            or None,
            health_reference=str(row.get("health_reference") or "") or None,
            risk_reference=str(row.get("risk_reference") or "") or None,
            lineage_reference=str(row.get("lineage_reference") or "") or None,
            provenance_reference=str(row.get("provenance_reference") or "") or None,
            version=int(row.get("version") or 1),
            search_attributes=search,
        )


class CloudAccountEnterpriseAdapter(DomainEnterpriseAdapter):
    entity_type = EntityType.CLOUD_ACCOUNT
    source_system = "cloud_account_registry"
    id_fields = ("account_id", "source_entity_id", "id")
    name_fields = ("account_name", "canonical_name", "display_name")


class ApplicationEnterpriseAdapter(DomainEnterpriseAdapter):
    entity_type = EntityType.APPLICATION
    source_system = "application_registry"
    id_fields = ("application_id", "app_id", "source_entity_id", "id")
    name_fields = ("application_name", "app_name", "name", "canonical_name")


class BusinessServiceEnterpriseAdapter(DomainEnterpriseAdapter):
    entity_type = EntityType.BUSINESS_SERVICE
    source_system = "business_service_registry"
    id_fields = ("business_service_id", "service_id", "source_entity_id", "id")
    name_fields = ("business_service_name", "service_name", "name", "canonical_name")


class TechnologyEnterpriseAdapter(DomainEnterpriseAdapter):
    entity_type = EntityType.TECHNOLOGY
    source_system = "technology_inventory"
    id_fields = ("technology_id", "tech_id", "source_entity_id", "id")
    name_fields = ("technology_name", "name", "canonical_name")


class SaaSEnterpriseAdapter(DomainEnterpriseAdapter):
    entity_type = EntityType.SAAS_PRODUCT
    source_system = "saas_governance"
    id_fields = ("saas_product_id", "tool_id", "source_entity_id", "id")
    name_fields = ("product_name", "tool_name", "name", "canonical_name")
