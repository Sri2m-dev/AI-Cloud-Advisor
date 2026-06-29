from __future__ import annotations

from typing import Any

import streamlit as st

from services.supabase_client import supabase


def _normalize(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _lower(value: Any) -> str:
    return _normalize(value).lower()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _first_existing(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _dedupe(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for row in rows:
        key = tuple(_lower(row.get(item)) for item in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


class DigitalTwinRepository:
    @staticmethod
    def _fetch_table(table_name: str) -> list[dict[str, Any]]:
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=300)
    def get_business_services() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("business_services")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_application_registry() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("application_registry")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_technology_inventory() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("technology_inventory")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_relationship_graph() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("relationship_graph")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_recommendations() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("recommendations")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_savings() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("mart_savings")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_renewal_risks() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("vw_saas_renewal_risk")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_license_costs() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("license_cost")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_saas_costs() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("saas_cost")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cloud_costs() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("unified_cloud_costs")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_enterprise_spend() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("mart_enterprise_spend_v2")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_cost_anomalies() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("cost_anomaly_org_view")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_approval_queue() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("approval_queue")

    @staticmethod
    @st.cache_data(ttl=300)
    def get_inactive_users() -> list[dict[str, Any]]:
        return DigitalTwinRepository._fetch_table("vw_inactive_saas_users")

    @staticmethod
    def _technology_name(row: dict[str, Any]) -> str:
        return _normalize(
            _first_existing(
                row,
                "technology_name",
                "name",
                "vendor_name",
                "provider",
                "service_name",
                default="Unknown Technology",
            )
        )

    @staticmethod
    def _technology_type(row: dict[str, Any]) -> str:
        value = _normalize(_first_existing(row, "technology_type", "type", "category", default="Technology"))
        value_l = value.lower()
        name_l = _lower(DigitalTwinRepository._technology_name(row))
        if value_l == "cloud" or name_l in {"aws", "azure", "gcp"}:
            return "Cloud"
        if value_l == "ai" or name_l in {"chatgpt enterprise", "github copilot", "copilot", "claude", "gemini", "cursor"}:
            return "AI"
        if "msp" in value_l or "managed" in value_l or "managed" in name_l:
            return "MSP"
        if value_l in {"saas", "monitoring", "productivity", "collaboration", "developer tools"}:
            return "SaaS"
        return value or "Technology"

    @staticmethod
    def _technology_relationship_type(technology_type: str) -> str:
        type_l = technology_type.lower()
        if type_l == "cloud":
            return "HOSTED_ON"
        if type_l == "ai":
            return "USES_AI"
        if type_l == "saas":
            return "USES_SAAS"
        if type_l == "msp":
            return "SUPPORTED_BY"
        return "DEPENDS_ON"

    @staticmethod
    def _primary_application() -> str:
        apps = DigitalTwinRepository.get_application_registry()
        for row in apps:
            app = _normalize(_first_existing(row, "app_name", "application_name", "application", "name"))
            if app:
                return app
        return "Checkout"

    @staticmethod
    def _primary_business_unit() -> str:
        for row in DigitalTwinRepository.get_application_registry():
            unit = _normalize(_first_existing(row, "business_unit", "department"))
            if unit:
                return unit
        return "Retail"

    @staticmethod
    def get_enterprise_nodes() -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []

        for row in DigitalTwinRepository.get_business_services():
            nodes.append({"name": row.get("service_name") or row.get("name") or "Order Processing", "type": "Business Service", "metadata": row})
        for row in DigitalTwinRepository.get_application_registry():
            nodes.append({"name": row.get("app_name") or row.get("application_name") or row.get("name") or "Checkout", "type": "Application", "metadata": row})
        for row in DigitalTwinRepository.get_technology_inventory():
            technology_name = DigitalTwinRepository._technology_name(row)
            technology_type = DigitalTwinRepository._technology_type(row)
            nodes.append({"name": technology_name, "type": technology_type, "metadata": row})

        nodes.extend(
            [
                {"name": "Retail", "type": "Business Unit", "metadata": {}},
                {"name": "Revenue Services", "type": "Revenue Stream", "metadata": {}},
                {"name": "Order Processing", "type": "Business Service", "metadata": {}},
                {"name": "Checkout", "type": "Application", "metadata": {}},
                {"name": "AWS", "type": "Technology", "metadata": {"technology_type": "Cloud"}},
                {"name": "Datadog", "type": "Technology", "metadata": {"technology_type": "SaaS"}},
                {"name": "GitHub", "type": "Technology", "metadata": {"technology_type": "SaaS"}},
                {"name": "ChatGPT Enterprise", "type": "Technology", "metadata": {"technology_type": "AI"}},
                {"name": "GitHub Copilot", "type": "Technology", "metadata": {"technology_type": "AI"}},
            ]
        )
        return _dedupe(nodes, ("name", "type"))

    @staticmethod
    def _normalize_relationship(row: dict[str, Any]) -> dict[str, Any] | None:
        source = _normalize(row.get("source_name") or row.get("source"))
        target = _normalize(row.get("target_name") or row.get("target"))
        if not source or not target:
            return None
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else dict(row)
        return {
            "source": source,
            "target": target,
            "relationship_type": _normalize(row.get("relationship_type") or row.get("relationship") or "DEPENDS_ON").upper(),
            "source_type": _normalize(row.get("source_type") or "Unknown"),
            "target_type": _normalize(row.get("target_type") or "Unknown"),
            "metadata": metadata,
        }

    @staticmethod
    def _discovered_relationships() -> list[dict[str, Any]]:
        application = DigitalTwinRepository._primary_application()
        unit = DigitalTwinRepository._primary_business_unit()
        relationships = [
            {"source": unit, "target": "Revenue Services", "relationship_type": "OWNS", "source_type": "Business Unit", "target_type": "Business Service", "metadata": {}},
            {"source": "Revenue Services", "target": application, "relationship_type": "USES", "source_type": "Business Service", "target_type": "Application", "metadata": {}},
        ]

        inventory = DigitalTwinRepository.get_technology_inventory()
        if not inventory:
            inventory = [
                {"technology_name": "AWS", "technology_type": "Cloud"},
                {"technology_name": "Datadog", "technology_type": "SaaS"},
                {"technology_name": "GitHub", "technology_type": "SaaS"},
                {"technology_name": "ChatGPT Enterprise", "technology_type": "AI"},
                {"technology_name": "GitHub Copilot", "technology_type": "AI"},
            ]

        for row in inventory:
            technology = DigitalTwinRepository._technology_name(row)
            if not technology or technology == "Unknown Technology":
                continue
            technology_type = DigitalTwinRepository._technology_type(row)
            relationships.append(
                {
                    "source": application,
                    "target": technology,
                    "relationship_type": DigitalTwinRepository._technology_relationship_type(technology_type),
                    "source_type": "Application",
                    "target_type": technology_type,
                    "metadata": {
                        "cost_domain": technology_type if technology_type in {"Cloud", "SaaS", "AI", "MSP"} else "License",
                        "source": "technology_inventory",
                    },
                }
            )

        return relationships

    @staticmethod
    def get_enterprise_relationships() -> list[dict[str, Any]]:
        graph_rows = [
            item for item in (
                DigitalTwinRepository._normalize_relationship(row)
                for row in DigitalTwinRepository.get_relationship_graph()
            )
            if item
        ]
        relationships = graph_rows + DigitalTwinRepository._discovered_relationships()

        return _dedupe(relationships, ("source", "relationship_type", "target", "source_type", "target_type"))

    @staticmethod
    def get_business_units() -> list[dict[str, Any]]:
        units = []
        for row in DigitalTwinRepository.get_application_registry():
            unit = row.get("business_unit") or row.get("department")
            if unit:
                units.append({"Business Unit": unit, "Source": "application_registry"})
        return units or [{"Business Unit": "Retail", "Source": "fallback"}]

    @staticmethod
    def get_service_map() -> list[dict[str, Any]]:
        return DigitalTwinRepository.get_business_services()

    @staticmethod
    def get_application_map() -> list[dict[str, Any]]:
        return DigitalTwinRepository.get_application_registry()

    @staticmethod
    def get_technology_map() -> list[dict[str, Any]]:
        return DigitalTwinRepository.get_technology_inventory()

    @staticmethod
    def get_risk_map() -> list[dict[str, Any]]:
        return DigitalTwinRepository.get_renewal_risks()

    @staticmethod
    def get_cost_map() -> list[dict[str, Any]]:
        return (
            DigitalTwinRepository.get_cloud_costs()
            + DigitalTwinRepository.get_saas_costs()
            + DigitalTwinRepository.get_license_costs()
            + DigitalTwinRepository.get_technology_inventory()
            + DigitalTwinRepository.get_enterprise_spend()
        )

    @staticmethod
    def get_savings_map() -> list[dict[str, Any]]:
        return DigitalTwinRepository.get_savings() or DigitalTwinRepository.get_recommendations()
