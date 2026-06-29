from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.supabase_client import supabase


class EnterpriseCostAttributionService:
    @staticmethod
    def sync_cost_attribution(organization_id: str | None = None) -> dict[str, Any]:
        context = EnterpriseCostAttributionService._load_context(organization_id)
        attribution_rows = [
            {
                **EnterpriseCostAttributionService._attribute_cost_row(cost_row, context),
                "organization_id": context["organization_id"],
            }
            for cost_row in context["cost_rows"]
        ]

        persistence_rows = EnterpriseCostAttributionService._persistence_rows(
            attribution_rows,
            context["organization_id"],
        )
        if persistence_rows:
            try:
                supabase.table("enterprise_cost_attribution").upsert(
                    persistence_rows,
                    on_conflict="organization_id,enterprise_asset_id,cloud,account_name,service_name,usage_date",
                ).execute()
            except Exception as exc:
                return {
                    "status": "FAILED",
                    "error": f"Failed to persist enterprise cost attribution: {exc}",
                    "rows_prepared": len(persistence_rows),
                }

        attributed = [row for row in attribution_rows if row.get("attributed")]
        total_cost = EnterpriseCostAttributionService._sum_cost(attribution_rows)
        attributed_cost = EnterpriseCostAttributionService._sum_cost(attributed)
        return {
            "status": "SUCCESS",
            "organization_id": context["organization_id"],
            "rows_processed": len(attribution_rows),
            "rows_persisted": len(persistence_rows),
            "attributed_rows": len(attributed),
            "unattributed_rows": max(len(attribution_rows) - len(attributed), 0),
            "total_cost": round(total_cost, 2),
            "attributed_cost": round(attributed_cost, 2),
            "unattributed_cost": round(max(total_cost - attributed_cost, 0), 2),
            "attribution_coverage_percent": EnterpriseCostAttributionService._percent(attributed_cost, total_cost),
            "attributions": attribution_rows,
        }

    @staticmethod
    def _persistence_rows(attribution_rows: list[dict[str, Any]], organization_id: str) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for row in attribution_rows:
            if not row.get("enterprise_asset_id"):
                continue
            owner = row.get("owner")
            rows.append(
                {
                    "organization_id": organization_id,
                    "enterprise_asset_id": row.get("enterprise_asset_id"),
                    "provider": row.get("cloud"),
                    "cloud": row.get("cloud"),
                    "account_name": row.get("account_name"),
                    "service_name": row.get("service_name"),
                    "usage_date": row.get("usage_date"),
                    "cost": row.get("cost") or 0,
                    "currency": row.get("currency") or "USD",
                    "application": row.get("application"),
                    "business_service": row.get("business_service"),
                    "business_capability": row.get("business_capability"),
                    "department": row.get("department"),
                    "business_unit": row.get("business_unit"),
                    "cost_center": row.get("cost_center"),
                    "technical_owner": owner,
                    "business_owner": owner,
                    "executive_owner": row.get("executive_owner"),
                    "attribution_source": row.get("attribution_source"),
                    "confidence": int(row.get("confidence") or 0),
                    "updated_at": now,
                }
            )
        return rows

    @staticmethod
    def get_cost_attribution_summary(organization_id: str | None = None) -> dict[str, Any]:
        return EnterpriseCostAttributionService.sync_cost_attribution(organization_id)

    @staticmethod
    def get_cost_by_application(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseCostAttributionService._cost_distribution(
            EnterpriseCostAttributionService.sync_cost_attribution(organization_id).get("attributions", []),
            "application",
            "Application",
        )

    @staticmethod
    def get_cost_by_business_service(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseCostAttributionService._cost_distribution(
            EnterpriseCostAttributionService.sync_cost_attribution(organization_id).get("attributions", []),
            "business_service",
            "Business Service",
        )

    @staticmethod
    def get_cost_by_business_capability(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseCostAttributionService._cost_distribution(
            EnterpriseCostAttributionService.sync_cost_attribution(organization_id).get("attributions", []),
            "business_capability",
            "Business Capability",
        )

    @staticmethod
    def get_cost_by_department(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseCostAttributionService._cost_distribution(
            EnterpriseCostAttributionService.sync_cost_attribution(organization_id).get("attributions", []),
            "department",
            "Department",
        )

    @staticmethod
    def get_cost_by_cost_center(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseCostAttributionService._cost_distribution(
            EnterpriseCostAttributionService.sync_cost_attribution(organization_id).get("attributions", []),
            "cost_center",
            "Cost Center",
        )

    @staticmethod
    def get_unattributed_costs(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = EnterpriseCostAttributionService.sync_cost_attribution(organization_id).get("attributions", [])
        return [row for row in rows if not row.get("attributed")]

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        summary = EnterpriseCostAttributionService.sync_cost_attribution(organization_id)
        rows = summary.get("attributions", [])
        return {
            "summary": summary,
            "cost_by_application": EnterpriseCostAttributionService._cost_distribution(rows, "application", "Application"),
            "cost_by_business_service": EnterpriseCostAttributionService._cost_distribution(
                rows,
                "business_service",
                "Business Service",
            ),
            "cost_by_business_capability": EnterpriseCostAttributionService._cost_distribution(
                rows,
                "business_capability",
                "Business Capability",
            ),
            "cost_by_department": EnterpriseCostAttributionService._cost_distribution(rows, "department", "Department"),
            "cost_by_cost_center": EnterpriseCostAttributionService._cost_distribution(rows, "cost_center", "Cost Center"),
            "unattributed_costs": [row for row in rows if not row.get("attributed")],
            "attributions": rows,
        }

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        resolved_org = resolve_organization_id(organization_id)
        assets = EnterpriseCostAttributionService._fetch_org_rows("enterprise_asset_identity", resolved_org)
        correlations = EnterpriseCostAttributionService._fetch_org_rows("enterprise_asset_correlation", resolved_org)
        ownership = EnterpriseCostAttributionService._fetch_org_rows("enterprise_asset_ownership", resolved_org)
        capabilities = EnterpriseCostAttributionService._fetch_org_rows("business_capability_registry", resolved_org)
        inventory = EnterpriseCostAttributionService._fetch_rows("technology_inventory")
        spend_mapping = EnterpriseCostAttributionService._fetch_rows("application_spend_mapping")
        cost_rows = EnterpriseCostAttributionService._fetch_rows("unified_cloud_costs")

        return {
            "organization_id": resolved_org,
            "cost_rows": cost_rows,
            "assets": assets,
            "assets_by_source_id": EnterpriseCostAttributionService._index_rows(assets, ["source_asset_id", "asset_uid"]),
            "correlations": correlations,
            "correlation_by_asset": EnterpriseCostAttributionService._index_rows(correlations, ["enterprise_asset_id"]),
            "correlation_by_application": EnterpriseCostAttributionService._index_rows(correlations, ["application"]),
            "correlations_by_vendor": EnterpriseCostAttributionService._group_rows(correlations, ["vendor", "cloud_account"]),
            "ownership": ownership,
            "ownership_by_asset": EnterpriseCostAttributionService._index_rows(ownership, ["enterprise_asset_id"]),
            "ownership_by_application": EnterpriseCostAttributionService._index_rows(ownership, ["application"]),
            "capability_by_name": EnterpriseCostAttributionService._index_rows(capabilities, ["capability_name"]),
            "inventory_by_provider": EnterpriseCostAttributionService._index_rows(
                inventory,
                ["technology_name", "vendor_name", "cloud_provider"],
            ),
            "spend_mapping": spend_mapping,
        }

    @staticmethod
    def _attribute_cost_row(cost_row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        source_asset_id = cost_row.get("resource_id")
        asset = context["assets_by_source_id"].get(EnterpriseCostAttributionService._norm(source_asset_id))
        if asset:
            return EnterpriseCostAttributionService._build_attribution(
                cost_row,
                context,
                asset.get("asset_uid"),
                "Enterprise Asset ID match",
                100,
            )

        application = EnterpriseCostAttributionService._first(cost_row, keys=["application", "app_name"])
        if application:
            correlation = context["correlation_by_application"].get(EnterpriseCostAttributionService._norm(application))
            if correlation:
                return EnterpriseCostAttributionService._build_attribution(
                    cost_row,
                    context,
                    correlation.get("enterprise_asset_id"),
                    "Application correlation",
                    95,
                    application=correlation.get("application"),
                )

        ownership = EnterpriseCostAttributionService._match_ownership(cost_row, context)
        if ownership:
            return EnterpriseCostAttributionService._build_attribution(
                cost_row,
                context,
                ownership.get("enterprise_asset_id"),
                "Ownership mapping",
                90,
                application=ownership.get("application"),
            )

        mapped_application = EnterpriseCostAttributionService._application_from_spend_mapping(cost_row, context)
        if mapped_application:
            correlation = context["correlation_by_application"].get(EnterpriseCostAttributionService._norm(mapped_application))
            ownership = context["ownership_by_application"].get(EnterpriseCostAttributionService._norm(mapped_application), {})
            enterprise_asset_id = (correlation or ownership).get("enterprise_asset_id")
            return EnterpriseCostAttributionService._build_attribution(
                cost_row,
                context,
                enterprise_asset_id,
                "Application spend mapping",
                85,
                application=mapped_application,
            )

        provider_match = EnterpriseCostAttributionService._provider_or_category_match(cost_row, context)
        if provider_match:
            return EnterpriseCostAttributionService._build_attribution(
                cost_row,
                context,
                provider_match.get("enterprise_asset_id"),
                "Service/category mapping",
                75,
                application=provider_match.get("application"),
            )

        return EnterpriseCostAttributionService._base_cost_row(cost_row, False)

    @staticmethod
    def _build_attribution(
        cost_row: dict[str, Any],
        context: dict[str, Any],
        enterprise_asset_id: str | None,
        source: str,
        confidence: float,
        application: str | None = None,
    ) -> dict[str, Any]:
        correlation = context["correlation_by_asset"].get(EnterpriseCostAttributionService._norm(enterprise_asset_id), {})
        if not correlation and application:
            correlation = context["correlation_by_application"].get(EnterpriseCostAttributionService._norm(application), {})
        ownership = context["ownership_by_asset"].get(EnterpriseCostAttributionService._norm(enterprise_asset_id), {})
        if not ownership and application:
            ownership = context["ownership_by_application"].get(EnterpriseCostAttributionService._norm(application), {})

        row = EnterpriseCostAttributionService._base_cost_row(cost_row, True)
        business_capability = (
            correlation.get("business_capability")
            or ownership.get("business_capability")
            or EnterpriseCostAttributionService._capability_from_registry(correlation, ownership, context)
        )
        row.update(
            {
                "enterprise_asset_id": enterprise_asset_id or correlation.get("enterprise_asset_id") or ownership.get("enterprise_asset_id"),
                "application": application or correlation.get("application") or ownership.get("application"),
                "business_service": correlation.get("business_service") or ownership.get("business_service"),
                "business_capability": business_capability,
                "department": ownership.get("department") or correlation.get("department"),
                "cost_center": ownership.get("cost_center") or correlation.get("cost_center"),
                "owner": ownership.get("technical_owner") or ownership.get("business_owner") or correlation.get("owner"),
                "executive_owner": ownership.get("executive_owner"),
                "environment": ownership.get("environment") or correlation.get("environment") or cost_row.get("environment"),
                "attribution_source": source,
                "confidence": confidence,
            }
        )
        if not row.get("application"):
            row["attributed"] = False
            row["attribution_source"] = "Unattributed"
            row["confidence"] = 0
        return row

    @staticmethod
    def _base_cost_row(cost_row: dict[str, Any], attributed: bool) -> dict[str, Any]:
        cost = float(cost_row.get("cost") or 0)
        return {
            "cost_id": cost_row.get("id"),
            "cloud": cost_row.get("cloud"),
            "account_name": cost_row.get("account_name"),
            "service_name": cost_row.get("service_name"),
            "service_category": cost_row.get("service_category"),
            "region": cost_row.get("region"),
            "resource_id": cost_row.get("resource_id"),
            "usage_date": cost_row.get("usage_date"),
            "cost": round(cost, 2),
            "currency": cost_row.get("currency") or "USD",
            "enterprise_asset_id": None,
            "application": None,
            "business_service": None,
            "business_capability": None,
            "department": None,
            "cost_center": None,
            "owner": None,
            "executive_owner": None,
            "environment": cost_row.get("environment"),
            "attributed": attributed,
            "attribution_source": "Unattributed" if not attributed else None,
            "confidence": 0,
        }

    @staticmethod
    def _match_ownership(cost_row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
        resource_id = EnterpriseCostAttributionService._norm(cost_row.get("resource_id"))
        application = EnterpriseCostAttributionService._norm(cost_row.get("application"))
        if resource_id and resource_id in context["ownership_by_asset"]:
            return context["ownership_by_asset"][resource_id]
        if application and application in context["ownership_by_application"]:
            return context["ownership_by_application"][application]
        return None

    @staticmethod
    def _application_from_spend_mapping(cost_row: dict[str, Any], context: dict[str, Any]) -> str | None:
        candidates = [
            cost_row.get("application"),
            cost_row.get("service_name"),
            cost_row.get("service_category"),
        ]
        normalized_candidates = {EnterpriseCostAttributionService._norm(value) for value in candidates if value}
        for mapping in context["spend_mapping"]:
            spend_name = EnterpriseCostAttributionService._norm(mapping.get("spend_application_name"))
            if spend_name in normalized_candidates:
                return mapping.get("registry_app_name") or mapping.get("spend_application_name")
        return None

    @staticmethod
    def _provider_or_category_match(cost_row: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
        provider = EnterpriseCostAttributionService._norm(cost_row.get("cloud") or cost_row.get("account_name"))
        if provider:
            matches = context["correlations_by_vendor"].get(provider) or []
            if matches:
                return EnterpriseCostAttributionService._highest_confidence(matches)

        account_name = EnterpriseCostAttributionService._norm(cost_row.get("account_name"))
        if account_name:
            for row in context["correlations"]:
                cloud_account = EnterpriseCostAttributionService._norm(row.get("cloud_account"))
                if cloud_account and (cloud_account in account_name or account_name in cloud_account):
                    return row

        service_name = EnterpriseCostAttributionService._norm(cost_row.get("service_name"))
        service_category = EnterpriseCostAttributionService._norm(cost_row.get("service_category"))
        for row in context["correlations"]:
            for key in ("application", "business_service", "business_capability"):
                value = EnterpriseCostAttributionService._norm(row.get(key))
                if value and (value in service_name or value in service_category):
                    return row
        return None

    @staticmethod
    def _capability_from_registry(
        correlation: dict[str, Any],
        ownership: dict[str, Any],
        context: dict[str, Any],
    ) -> str | None:
        for candidate in (correlation.get("business_capability"), ownership.get("business_capability")):
            if context["capability_by_name"].get(EnterpriseCostAttributionService._norm(candidate)):
                return candidate
        return correlation.get("business_capability") or ownership.get("business_capability")

    @staticmethod
    def _cost_distribution(rows: list[dict[str, Any]], field: str, label: str) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not row.get("attributed"):
                continue
            key = row.get(field) or "Unassigned"
            item = grouped.setdefault(
                key,
                {
                    label: key,
                    "Cost": 0.0,
                    "Rows": 0,
                    "Applications": set(),
                    "Business Capabilities": set(),
                },
            )
            item["Cost"] += float(row.get("cost") or 0)
            item["Rows"] += 1
            if row.get("application"):
                item["Applications"].add(row["application"])
            if row.get("business_capability"):
                item["Business Capabilities"].add(row["business_capability"])

        output = []
        for item in grouped.values():
            item["Cost"] = round(item["Cost"], 2)
            item["Applications"] = len(item["Applications"])
            item["Business Capabilities"] = len(item["Business Capabilities"])
            output.append(item)
        return sorted(output, key=lambda row: row["Cost"], reverse=True)

    @staticmethod
    def _fetch_rows(table_name: str) -> list[dict[str, Any]]:
        try:
            return supabase.table(table_name).select("*").limit(1000).execute().data or []
        except Exception as exc:
            print(f"ENTERPRISE COST ATTRIBUTION LOAD FAILED: {table_name}: {exc}")
            return []

    @staticmethod
    def _fetch_org_rows(table_name: str, organization_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", organization_id)
                .limit(1000)
                .execute()
                .data
                or []
            )
            if rows:
                return rows
        except Exception as exc:
            print(f"ENTERPRISE COST ATTRIBUTION ORG LOAD FAILED: {table_name}: {exc}")
        return EnterpriseCostAttributionService._fetch_rows(table_name)

    @staticmethod
    def _index_rows(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, dict[str, Any]]:
        index = {}
        for row in rows:
            for key in keys:
                value = EnterpriseCostAttributionService._norm(row.get(key))
                if value and value not in index:
                    index[value] = row
        return index

    @staticmethod
    def _group_rows(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            for key in keys:
                value = EnterpriseCostAttributionService._norm(row.get(key))
                if value:
                    grouped.setdefault(value, []).append(row)
        return grouped

    @staticmethod
    def _highest_confidence(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return sorted(rows, key=lambda row: float(row.get("confidence") or 0), reverse=True)[0]

    @staticmethod
    def _sum_cost(rows: list[dict[str, Any]]) -> float:
        return sum(float(row.get("cost") or 0) for row in rows)

    @staticmethod
    def _percent(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return round((float(numerator) / float(denominator)) * 100, 2)

    @staticmethod
    def _first(*rows: dict[str, Any], keys: list[str]) -> Any:
        for row in rows:
            for key in keys:
                value = row.get(key)
                if value not in (None, ""):
                    return value
        return None

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()
