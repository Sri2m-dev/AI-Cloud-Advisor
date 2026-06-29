from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class EnterpriseCorrelationService:
    TABLE_NAME = "enterprise_asset_correlation"

    @staticmethod
    def correlate_assets(organization_id: str | None = None) -> dict[str, Any]:
        context = EnterpriseCorrelationService._load_context(organization_id)
        correlations = [
            EnterpriseCorrelationService._correlate_asset(asset, context)
            for asset in context["assets"]
        ]
        correlated = [row for row in correlations if row.get("application")]
        EnterpriseCorrelationService._persist_correlations(correlations)
        return {
            "status": "SUCCESS",
            "organization_id": context["organization_id"],
            "assets_processed": len(correlations),
            "correlated": len(correlated),
            "uncorrelated": max(len(correlations) - len(correlated), 0),
            "correlation_percent": EnterpriseCorrelationService._percent(len(correlated), len(correlations)),
            "average_confidence": EnterpriseCorrelationService._average(
                [float(row.get("confidence") or 0) for row in correlated]
            ),
            "correlations": correlations,
        }

    @staticmethod
    def get_correlation_summary(organization_id: str | None = None) -> dict[str, Any]:
        rows = EnterpriseCorrelationService._load_correlations(organization_id)
        if not rows:
            return EnterpriseCorrelationService.correlate_assets(organization_id)

        correlated = [row for row in rows if row.get("application")]
        return {
            "status": "SUCCESS",
            "organization_id": resolve_organization_id(organization_id),
            "assets_processed": len(rows),
            "correlated": len(correlated),
            "uncorrelated": max(len(rows) - len(correlated), 0),
            "correlation_percent": EnterpriseCorrelationService._percent(len(correlated), len(rows)),
            "average_confidence": EnterpriseCorrelationService._average(
                [float(row.get("confidence") or 0) for row in correlated]
            ),
            "correlations": rows,
        }

    @staticmethod
    def get_uncorrelated_assets(organization_id: str | None = None) -> list[dict[str, Any]]:
        summary = EnterpriseCorrelationService.get_correlation_summary(organization_id)
        return [row for row in summary.get("correlations", []) if not row.get("application")]

    @staticmethod
    def get_low_confidence_correlations(
        organization_id: str | None = None,
        threshold: float = 90,
    ) -> list[dict[str, Any]]:
        summary = EnterpriseCorrelationService.get_correlation_summary(organization_id)
        return [
            row
            for row in summary.get("correlations", [])
            if row.get("application") and float(row.get("confidence") or 0) < threshold
        ]

    @staticmethod
    def get_application_distribution(organization_id: str | None = None) -> list[dict[str, Any]]:
        summary = EnterpriseCorrelationService.get_correlation_summary(organization_id)
        return EnterpriseCorrelationService._distribution(summary.get("correlations", []), "application", "Application")

    @staticmethod
    def get_business_service_distribution(organization_id: str | None = None) -> list[dict[str, Any]]:
        summary = EnterpriseCorrelationService.get_correlation_summary(organization_id)
        return EnterpriseCorrelationService._distribution(
            summary.get("correlations", []),
            "business_service",
            "Business Service",
        )

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        summary = EnterpriseCorrelationService.get_correlation_summary(organization_id)
        return {
            "summary": summary,
            "top_applications": EnterpriseCorrelationService.get_application_distribution(organization_id)[:5],
            "top_business_services": EnterpriseCorrelationService.get_business_service_distribution(organization_id)[:5],
            "low_confidence": EnterpriseCorrelationService.get_low_confidence_correlations(organization_id),
            "uncorrelated_assets": EnterpriseCorrelationService.get_uncorrelated_assets(organization_id),
        }

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        requested_org = str(organization_id or "").strip() or None
        resolved_org = resolve_organization_id(requested_org)
        assets = EnterpriseCorrelationService._load_assets(resolved_org)
        if requested_org and not assets:
            resolved_org = resolve_organization_id()
            assets = EnterpriseCorrelationService._load_assets(resolved_org)

        discovered = EnterpriseCorrelationService._fetch_org_rows("discovered_assets", resolved_org)
        inventory = EnterpriseCorrelationService._fetch_org_rows("technology_inventory", resolved_org)
        app_registry = EnterpriseCorrelationService._fetch_rows("application_registry")
        business_services = EnterpriseCorrelationService._fetch_rows("business_services")
        app_spend_mapping = EnterpriseCorrelationService._fetch_rows("application_spend_mapping")
        technology_relationships = EnterpriseCorrelationService._fetch_org_rows("technology_relationships", resolved_org)
        relationship_graph = EnterpriseCorrelationService._fetch_org_rows("relationship_graph", resolved_org)
        business_service_relationships = EnterpriseCorrelationService._fetch_rows("business_service_relationships")

        discovered_by_source = {
            EnterpriseCorrelationService._norm(row.get("asset_id")): row
            for row in discovered
            if row.get("asset_id")
        }
        inventory_by_name = EnterpriseCorrelationService._index_rows(
            inventory,
            ["technology_name", "vendor_name", "cloud_provider"],
        )

        return {
            "organization_id": resolved_org,
            "assets": assets,
            "discovered_by_source": discovered_by_source,
            "inventory_by_name": inventory_by_name,
            "applications": app_registry,
            "application_by_name": EnterpriseCorrelationService._index_rows(app_registry, ["app_name", "app_code"]),
            "business_services": business_services,
            "business_service_by_name": EnterpriseCorrelationService._index_rows(
                business_services,
                ["service_name", "business_service_name", "name"],
            ),
            "application_spend_mapping": app_spend_mapping,
            "relationships": technology_relationships + relationship_graph + business_service_relationships,
        }

    @staticmethod
    def _correlate_asset(asset: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        discovered = context["discovered_by_source"].get(
            EnterpriseCorrelationService._norm(asset.get("source_asset_id")),
            {},
        )
        raw_payload = discovered.get("raw_payload") or {}
        if not isinstance(raw_payload, dict):
            raw_payload = {}

        app_result = EnterpriseCorrelationService._infer_application(asset, discovered, raw_payload, context)
        application = app_result["application"]
        app_row = context["application_by_name"].get(EnterpriseCorrelationService._norm(application), {})
        business_service = EnterpriseCorrelationService._infer_business_service(application, context)
        business_capability = EnterpriseCorrelationService._infer_business_capability(application, business_service, context)
        service_row = context["business_service_by_name"].get(EnterpriseCorrelationService._norm(business_service), {})
        inventory_row = EnterpriseCorrelationService._matching_inventory(asset, context)
        owner = EnterpriseCorrelationService._first(
            app_row,
            service_row,
            inventory_row,
            raw_payload,
            keys=["owner_name", "service_owner", "business_owner", "technical_owner", "owner"],
        )
        department = EnterpriseCorrelationService._first(
            app_row,
            service_row,
            raw_payload,
            inventory_row,
            keys=["department", "owner_department", "business_unit"],
        )
        team = EnterpriseCorrelationService._first(app_row, raw_payload, keys=["team_name", "team"])
        cost_center = EnterpriseCorrelationService._first(app_row, raw_payload, keys=["cost_center", "costCenter"])
        environment = EnterpriseCorrelationService._infer_environment(asset, discovered, raw_payload, app_row)
        cloud_account = EnterpriseCorrelationService._first(discovered, raw_payload, keys=["account_id", "account_name"])
        vendor = EnterpriseCorrelationService._first(
            asset,
            inventory_row,
            raw_payload,
            keys=["provider", "vendor_name", "cloud_provider"],
        )
        ai_services = EnterpriseCorrelationService._infer_ai_services(application, context)

        now = datetime.now(timezone.utc).isoformat()
        return {
            "enterprise_asset_id": asset.get("asset_uid"),
            "organization_id": context["organization_id"],
            "application": application,
            "business_service": business_service,
            "business_capability": business_capability,
            "department": department,
            "team": team,
            "owner": owner,
            "environment": environment,
            "cost_center": cost_center,
            "cloud_account": cloud_account,
            "vendor": vendor,
            "ai_services": ai_services,
            "confidence": app_result["confidence"],
            "correlation_source": app_result["source"],
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _infer_application(
        asset: dict[str, Any],
        discovered: dict[str, Any],
        raw_payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        applications = [row.get("app_name") for row in context["applications"] if row.get("app_name")]
        app_names = {EnterpriseCorrelationService._norm(name): name for name in applications}

        tag_value = EnterpriseCorrelationService._first(
            raw_payload,
            discovered,
            keys=["Application", "application", "app_name", "registry_app_name"],
        )
        if EnterpriseCorrelationService._norm(tag_value) in app_names:
            return {"application": app_names[EnterpriseCorrelationService._norm(tag_value)], "confidence": 95, "source": "Application tag"}

        existing = EnterpriseCorrelationService._application_from_existing_mapping(asset, context, app_names)
        if existing:
            return {"application": existing, "confidence": 100, "source": "Existing mapping"}

        asset_text = " ".join(
            str(value or "")
            for value in [
                asset.get("asset_name"),
                asset.get("source_asset_id"),
                raw_payload.get("technology_name"),
                discovered.get("asset_name"),
            ]
        )
        for normalized, app_name in app_names.items():
            if normalized and normalized in EnterpriseCorrelationService._norm(asset_text):
                return {"application": app_name, "confidence": 90, "source": "Naming convention"}

        return {"application": None, "confidence": 0, "source": "Uncorrelated"}

    @staticmethod
    def _application_from_existing_mapping(
        asset: dict[str, Any],
        context: dict[str, Any],
        app_names: dict[str, str],
    ) -> str | None:
        aliases = EnterpriseCorrelationService._asset_aliases(asset)
        provider = EnterpriseCorrelationService._norm(asset.get("provider"))
        connector = EnterpriseCorrelationService._norm(asset.get("connector_name"))

        for row in context["application_spend_mapping"]:
            spend_name = EnterpriseCorrelationService._norm(row.get("spend_application_name"))
            registry_name = EnterpriseCorrelationService._norm(row.get("registry_app_name"))
            if spend_name in aliases and registry_name in app_names:
                return app_names[registry_name]

        for row in context["relationships"]:
            source_name = EnterpriseCorrelationService._norm(row.get("source_name") or row.get("source"))
            target_name = EnterpriseCorrelationService._norm(row.get("target_name") or row.get("target"))
            source_type = EnterpriseCorrelationService._norm(row.get("source_type"))
            target_type = EnterpriseCorrelationService._norm(row.get("target_type"))

            if source_type == "application" and target_name in aliases | {provider, connector} and source_name in app_names:
                return app_names[source_name]
            if target_type == "application" and source_name in aliases | {provider, connector} and target_name in app_names:
                return app_names[target_name]
            if source_name in app_names and target_name in aliases | {provider, connector}:
                return app_names[source_name]
            if target_name in app_names and source_name in aliases | {provider, connector}:
                return app_names[target_name]

        return None

    @staticmethod
    def _infer_business_service(application: str | None, context: dict[str, Any]) -> str | None:
        if not application:
            return None
        app_key = EnterpriseCorrelationService._norm(application)
        if app_key == "checkout":
            return "Order Processing"

        for row in context["relationships"]:
            source_name = row.get("source_name") or row.get("source")
            target_name = row.get("target_name") or row.get("target")
            source_type = EnterpriseCorrelationService._norm(row.get("source_type"))
            target_type = EnterpriseCorrelationService._norm(row.get("target_type"))
            if EnterpriseCorrelationService._norm(target_name) == app_key and "service" in source_type:
                service = str(source_name or "").strip()
                return service
            if EnterpriseCorrelationService._norm(source_name) == app_key and "service" in target_type:
                return str(target_name or "").strip()
        return None

    @staticmethod
    def _infer_business_capability(
        application: str | None,
        business_service: str | None,
        context: dict[str, Any],
    ) -> str | None:
        if application and EnterpriseCorrelationService._norm(application) == "checkout":
            return "Revenue Services"
        service_key = EnterpriseCorrelationService._norm(business_service)
        for row in context["relationships"]:
            source_type = EnterpriseCorrelationService._norm(row.get("source_type"))
            target_type = EnterpriseCorrelationService._norm(row.get("target_type"))
            target_name = EnterpriseCorrelationService._norm(row.get("target_name") or row.get("target"))
            if service_key and service_key == target_name and "service" in target_type:
                return str(row.get("source_name") or row.get("source") or "").strip() or None
        return None

    @staticmethod
    def _infer_environment(
        asset: dict[str, Any],
        discovered: dict[str, Any],
        raw_payload: dict[str, Any],
        app_row: dict[str, Any],
    ) -> str | None:
        explicit = EnterpriseCorrelationService._first(raw_payload, discovered, app_row, keys=["environment", "env"])
        if explicit:
            return explicit
        text = EnterpriseCorrelationService._norm(
            " ".join(str(value or "") for value in [asset.get("asset_name"), asset.get("source_asset_id")])
        )
        if "-prod" in text or text.endswith("prod"):
            return "Production"
        if "-dev" in text or text.endswith("dev"):
            return "Development"
        if "-test" in text or "-qa" in text or text.endswith("test"):
            return "Testing"
        return None

    @staticmethod
    def _infer_ai_services(application: str | None, context: dict[str, Any]) -> list[str]:
        if not application:
            return []
        app_key = EnterpriseCorrelationService._norm(application)
        ai_services = []
        for row in context["relationships"]:
            source_name = EnterpriseCorrelationService._norm(row.get("source_name") or row.get("source"))
            target_type = EnterpriseCorrelationService._norm(row.get("target_type"))
            relationship_type = EnterpriseCorrelationService._norm(row.get("relationship_type"))
            if source_name == app_key and ("ai" in target_type or "ai" in relationship_type):
                target = str(row.get("target_name") or row.get("target") or "").strip()
                if target:
                    ai_services.append(target)
        return sorted(set(ai_services))

    @staticmethod
    def _persist_correlations(rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            supabase.table(EnterpriseCorrelationService.TABLE_NAME).upsert(
                rows,
                on_conflict="enterprise_asset_id",
            ).execute()
        except Exception as exc:
            print("ENTERPRISE ASSET CORRELATION UPSERT FAILED:", exc)

    @staticmethod
    def _load_correlations(organization_id: str | None = None) -> list[dict[str, Any]]:
        try:
            org_id = resolve_organization_id(organization_id)
            response = (
                supabase.table(EnterpriseCorrelationService.TABLE_NAME)
                .select("*")
                .eq("organization_id", org_id)
                .execute()
            )
            rows = response.data or []
            if rows:
                return rows
            if organization_id:
                fallback_org = resolve_organization_id()
                response = (
                    supabase.table(EnterpriseCorrelationService.TABLE_NAME)
                    .select("*")
                    .eq("organization_id", fallback_org)
                    .execute()
                )
                return response.data or []
            return []
        except Exception as exc:
            print("ENTERPRISE ASSET CORRELATION LOAD FAILED:", exc)
            return []

    @staticmethod
    def _load_assets(organization_id: str) -> list[dict[str, Any]]:
        return EnterpriseCorrelationService._fetch_org_rows("enterprise_asset_identity", organization_id)

    @staticmethod
    def _fetch_org_rows(table_name: str, organization_id: str) -> list[dict[str, Any]]:
        try:
            response = (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
            )
            rows = response.data or []
            if rows:
                return rows
            response = (
                supabase.table(table_name)
                .select("*")
                .is_("organization_id", "null")
                .execute()
            )
            return response.data or []
        except Exception as exc:
            print(f"ENTERPRISE CORRELATION {table_name} LOAD FAILED:", exc)
            return []

    @staticmethod
    def _fetch_rows(table_name: str) -> list[dict[str, Any]]:
        try:
            response = supabase.table(table_name).select("*").execute()
            return response.data or []
        except Exception as exc:
            print(f"ENTERPRISE CORRELATION {table_name} LOAD FAILED:", exc)
            return []

    @staticmethod
    def _matching_inventory(asset: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        for alias in EnterpriseCorrelationService._asset_aliases(asset):
            if alias in context["inventory_by_name"]:
                return context["inventory_by_name"][alias]
        return {}

    @staticmethod
    def _asset_aliases(asset: dict[str, Any]) -> set[str]:
        return {
            item
            for item in [
                EnterpriseCorrelationService._norm(asset.get("asset_uid")),
                EnterpriseCorrelationService._norm(asset.get("source_asset_id")),
                EnterpriseCorrelationService._norm(asset.get("asset_name")),
                EnterpriseCorrelationService._norm(asset.get("provider")),
                EnterpriseCorrelationService._norm(asset.get("connector_name")),
            ]
            if item
        }

    @staticmethod
    def _index_rows(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
        indexed = {}
        for row in rows:
            for field in fields:
                key = EnterpriseCorrelationService._norm(row.get(field))
                if key:
                    indexed[key] = row
        return indexed

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], field: str, label: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(field)
            if not value:
                continue
            counts[str(value)] = counts.get(str(value), 0) + 1
        return [
            {label: name, "Assets": count}
            for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]

    @staticmethod
    def _first(*rows: dict[str, Any], keys: list[str]) -> str | None:
        for row in rows:
            for key in keys:
                value = row.get(key) if row else None
                if value not in (None, ""):
                    return str(value)
        return None

    @staticmethod
    def _percent(numerator: int, denominator: int) -> float:
        return round((numerator / denominator) * 100, 1) if denominator else 0.0

    @staticmethod
    def _average(values: list[float]) -> float:
        return round(sum(values) / len(values), 1) if values else 0.0

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()
