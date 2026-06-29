from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.enterprise_correlation_service import EnterpriseCorrelationService
from services.supabase_client import supabase


class EnterpriseOwnershipService:
    TABLE_NAME = "enterprise_asset_ownership"
    QUALITY_FIELDS = [
        "technical_owner",
        "business_owner",
        "executive_owner",
        "department",
        "cost_center",
        "criticality",
        "lifecycle",
    ]

    @staticmethod
    def sync_asset_ownership(organization_id: str | None = None) -> dict[str, Any]:
        context = EnterpriseOwnershipService._load_context(organization_id)
        ownership_rows = [
            EnterpriseOwnershipService._build_ownership_row(asset, context)
            for asset in context["assets"]
        ]
        EnterpriseOwnershipService._persist_ownership(ownership_rows)
        owned = [row for row in ownership_rows if row.get("technical_owner") or row.get("business_owner")]
        return {
            "status": "SUCCESS",
            "organization_id": context["organization_id"],
            "assets_processed": len(ownership_rows),
            "owned_assets": len(owned),
            "ownership_coverage_percent": EnterpriseOwnershipService._percent(len(owned), len(ownership_rows)),
            "ownership_quality_score": EnterpriseOwnershipService._average(
                [float(row.get("ownership_score") or 0) for row in ownership_rows]
            ),
            "ownership": ownership_rows,
        }

    @staticmethod
    def get_ownership_summary(organization_id: str | None = None) -> dict[str, Any]:
        rows = EnterpriseOwnershipService._load_ownership(organization_id)
        if not rows:
            return EnterpriseOwnershipService.sync_asset_ownership(organization_id)
        owned = [row for row in rows if row.get("technical_owner") or row.get("business_owner")]
        return {
            "status": "SUCCESS",
            "organization_id": rows[0].get("organization_id") if rows else resolve_organization_id(organization_id),
            "assets_processed": len(rows),
            "owned_assets": len(owned),
            "ownership_coverage_percent": EnterpriseOwnershipService._percent(len(owned), len(rows)),
            "ownership_quality_score": EnterpriseOwnershipService._average(
                [float(row.get("ownership_score") or 0) for row in rows]
            ),
            "ownership": rows,
        }

    @staticmethod
    def get_assets_without_owner(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = EnterpriseOwnershipService.get_ownership_summary(organization_id).get("ownership", [])
        return [
            row
            for row in rows
            if not row.get("technical_owner") or not row.get("business_owner") or not row.get("executive_owner")
        ]

    @staticmethod
    def get_department_distribution(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseOwnershipService._distribution(
            EnterpriseOwnershipService.get_ownership_summary(organization_id).get("ownership", []),
            "department",
            "Department",
        )

    @staticmethod
    def get_owner_workload(organization_id: str | None = None) -> list[dict[str, Any]]:
        rows = EnterpriseOwnershipService.get_ownership_summary(organization_id).get("ownership", [])
        counts: dict[str, dict[str, Any]] = {}
        for row in rows:
            owner = row.get("technical_owner") or "Unassigned"
            item = counts.setdefault(owner, {"Technical Owner": owner, "Assets": 0, "Critical Assets": 0})
            item["Assets"] += 1
            if str(row.get("criticality") or "").lower() in {"critical", "tier 1", "tier1", "high"}:
                item["Critical Assets"] += 1
        return sorted(counts.values(), key=lambda item: item["Assets"], reverse=True)

    @staticmethod
    def get_cost_center_distribution(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseOwnershipService._distribution(
            EnterpriseOwnershipService.get_ownership_summary(organization_id).get("ownership", []),
            "cost_center",
            "Cost Center",
        )

    @staticmethod
    def get_business_capability_distribution(organization_id: str | None = None) -> list[dict[str, Any]]:
        return EnterpriseOwnershipService._distribution(
            EnterpriseOwnershipService.get_ownership_summary(organization_id).get("ownership", []),
            "business_capability",
            "Business Capability",
        )

    @staticmethod
    def get_dashboard(organization_id: str | None = None) -> dict[str, Any]:
        summary = EnterpriseOwnershipService.get_ownership_summary(organization_id)
        rows = summary.get("ownership", [])
        missing_executive = [row for row in rows if not row.get("executive_owner")]
        missing_cost_center = [row for row in rows if not row.get("cost_center")]
        manual_review = [
            row
            for row in rows
            if not row.get("reviewed") or float(row.get("ownership_score") or 0) < 100
        ]
        return {
            "summary": summary,
            "department_distribution": EnterpriseOwnershipService.get_department_distribution(summary["organization_id"]),
            "owner_workload": EnterpriseOwnershipService.get_owner_workload(summary["organization_id"]),
            "cost_center_distribution": EnterpriseOwnershipService.get_cost_center_distribution(summary["organization_id"]),
            "business_capability_distribution": EnterpriseOwnershipService.get_business_capability_distribution(
                summary["organization_id"]
            ),
            "team_distribution": EnterpriseOwnershipService._distribution(rows, "team", "Team"),
            "executive_owner_distribution": EnterpriseOwnershipService._distribution(rows, "executive_owner", "Executive Owner"),
            "assets_without_owner": EnterpriseOwnershipService.get_assets_without_owner(summary["organization_id"]),
            "missing_executive_owner": missing_executive,
            "missing_cost_center": missing_cost_center,
            "manual_review_queue": manual_review,
        }

    @staticmethod
    def update_ownership(
        enterprise_asset_id: str,
        updates: dict[str, Any],
        organization_id: str | None = None,
        reviewed_by: str | None = None,
    ) -> dict[str, Any]:
        row = EnterpriseOwnershipService._get_ownership_row(enterprise_asset_id, organization_id)
        if not row:
            EnterpriseOwnershipService.sync_asset_ownership(organization_id)
            row = EnterpriseOwnershipService._get_ownership_row(enterprise_asset_id, organization_id)
        if not row:
            return {"status": "FAILED", "message": "Ownership row not found"}

        now = datetime.now(timezone.utc).isoformat()
        allowed = {
            "technical_owner",
            "business_owner",
            "executive_owner",
            "department",
            "team",
            "cost_center",
            "criticality",
            "lifecycle",
            "reviewed",
        }
        payload = {key: value for key, value in updates.items() if key in allowed and value not in (None, "")}
        payload["source"] = "Manual"
        payload["confidence"] = 100
        payload["updated_at"] = now
        merged = {**row, **payload}
        payload["ownership_score"] = EnterpriseOwnershipService._ownership_score(merged)
        if payload.get("reviewed"):
            payload["reviewed_by"] = reviewed_by or "system"
            payload["reviewed_at"] = now

        try:
            supabase.table(EnterpriseOwnershipService.TABLE_NAME).update(payload).eq(
                "enterprise_asset_id",
                enterprise_asset_id,
            ).execute()
        except Exception as exc:
            print("ENTERPRISE OWNERSHIP UPDATE FAILED:", exc)
            return {"status": "FAILED", "message": str(exc)}
        return {"status": "SUCCESS", "message": f"{enterprise_asset_id} ownership updated", "row": {**row, **payload}}

    @staticmethod
    def bulk_update_ownership(
        enterprise_asset_ids: list[str],
        updates: dict[str, Any],
        organization_id: str | None = None,
        reviewed_by: str | None = None,
    ) -> dict[str, Any]:
        results = [
            EnterpriseOwnershipService.update_ownership(asset_id, updates, organization_id, reviewed_by)
            for asset_id in enterprise_asset_ids
            if asset_id
        ]
        return {
            "status": "SUCCESS" if all(item.get("status") == "SUCCESS" for item in results) else "PARTIAL",
            "updated": sum(1 for item in results if item.get("status") == "SUCCESS"),
            "failed": sum(1 for item in results if item.get("status") != "SUCCESS"),
            "results": results,
        }

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        correlation = EnterpriseCorrelationService.correlate_assets(organization_id)
        org_id = correlation["organization_id"]
        discovered = EnterpriseOwnershipService._fetch_org_rows("discovered_assets", org_id)
        inventory = EnterpriseOwnershipService._fetch_org_rows("technology_inventory", org_id)
        applications = EnterpriseOwnershipService._fetch_rows("application_registry")
        services = EnterpriseOwnershipService._fetch_rows("business_services")
        overrides = EnterpriseOwnershipService._load_ownership(org_id)
        return {
            "organization_id": org_id,
            "assets": correlation.get("correlations", []),
            "discovered_by_asset": EnterpriseOwnershipService._index_rows(discovered, ["asset_id", "asset_name"]),
            "inventory_by_name": EnterpriseOwnershipService._index_rows(inventory, ["technology_name", "vendor_name"]),
            "applications_by_name": EnterpriseOwnershipService._index_rows(applications, ["app_name", "app_code"]),
            "services_by_name": EnterpriseOwnershipService._index_rows(services, ["service_name", "business_service_name", "name"]),
            "overrides_by_asset": {
                str(row.get("enterprise_asset_id")): row
                for row in overrides
                if row.get("source") == "Manual" and row.get("enterprise_asset_id")
            },
        }

    @staticmethod
    def _build_ownership_row(asset: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        existing = context["overrides_by_asset"].get(asset.get("enterprise_asset_id"), {})
        app = context["applications_by_name"].get(EnterpriseOwnershipService._norm(asset.get("application")), {})
        service = context["services_by_name"].get(EnterpriseOwnershipService._norm(asset.get("business_service")), {})
        discovered = context["discovered_by_asset"].get(EnterpriseOwnershipService._norm(asset.get("enterprise_asset_id")), {})
        inventory = context["inventory_by_name"].get(EnterpriseOwnershipService._norm(asset.get("vendor")), {})
        raw_payload = discovered.get("raw_payload") or {}
        if not isinstance(raw_payload, dict):
            raw_payload = {}

        source = "Manual" if existing else "Application Registry" if app else "Business Service Mapping" if service else "Connector Tags"
        confidence = 100 if existing else 95 if app else 90 if service else 80
        technical_owner = EnterpriseOwnershipService._pick(
            existing,
            app,
            service,
            raw_payload,
            inventory,
            keys=["technical_owner", "owner_name", "service_owner", "business_owner"],
        )
        business_owner = EnterpriseOwnershipService._pick(
            existing,
            app,
            service,
            raw_payload,
            inventory,
            keys=["business_owner", "owner_name", "service_owner"],
        )
        row = {
            "organization_id": context["organization_id"],
            "enterprise_asset_id": asset.get("enterprise_asset_id"),
            "application": EnterpriseOwnershipService._pick(existing, asset, keys=["application"]),
            "business_service": EnterpriseOwnershipService._pick(existing, asset, keys=["business_service"]),
            "business_capability": EnterpriseOwnershipService._pick(existing, asset, keys=["business_capability"]),
            "department": EnterpriseOwnershipService._pick(existing, app, service, asset, raw_payload, keys=["department", "business_unit", "owner_department"]),
            "team": EnterpriseOwnershipService._pick(existing, app, raw_payload, keys=["team", "team_name"]),
            "technical_owner": technical_owner,
            "business_owner": business_owner,
            "executive_owner": EnterpriseOwnershipService._pick(existing, raw_payload, keys=["executive_owner", "executive"]) or "CIO",
            "cost_center": EnterpriseOwnershipService._pick(existing, app, asset, raw_payload, keys=["cost_center", "costCenter"]),
            "environment": EnterpriseOwnershipService._pick(existing, app, asset, raw_payload, keys=["environment", "env"]),
            "criticality": EnterpriseOwnershipService._pick(existing, app, service, raw_payload, keys=["criticality", "service_criticality"]) or "Standard",
            "lifecycle": EnterpriseOwnershipService._pick(existing, raw_payload, keys=["lifecycle", "lifecycle_status"]) or "Active",
            "source": source,
            "confidence": confidence,
            "reviewed": bool(existing.get("reviewed")) if existing else False,
            "reviewed_by": existing.get("reviewed_by"),
            "reviewed_at": existing.get("reviewed_at"),
            "created_at": existing.get("created_at") or datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        row["ownership_score"] = EnterpriseOwnershipService._ownership_score(row)
        return row

    @staticmethod
    def _persist_ownership(rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        try:
            supabase.table(EnterpriseOwnershipService.TABLE_NAME).upsert(
                rows,
                on_conflict="enterprise_asset_id",
            ).execute()
        except Exception as exc:
            print("ENTERPRISE OWNERSHIP UPSERT FAILED:", exc)

    @staticmethod
    def _load_ownership(organization_id: str | None = None) -> list[dict[str, Any]]:
        try:
            org_id = resolve_organization_id(organization_id)
            rows = (
                supabase.table(EnterpriseOwnershipService.TABLE_NAME)
                .select("*")
                .eq("organization_id", org_id)
                .execute()
                .data
                or []
            )
            if rows:
                return rows
            if organization_id:
                fallback = resolve_organization_id()
                return (
                    supabase.table(EnterpriseOwnershipService.TABLE_NAME)
                    .select("*")
                    .eq("organization_id", fallback)
                    .execute()
                    .data
                    or []
                )
            return []
        except Exception as exc:
            print("ENTERPRISE OWNERSHIP LOAD FAILED:", exc)
            return []

    @staticmethod
    def _get_ownership_row(enterprise_asset_id: str, organization_id: str | None = None) -> dict[str, Any] | None:
        rows = EnterpriseOwnershipService._load_ownership(organization_id)
        for row in rows:
            if row.get("enterprise_asset_id") == enterprise_asset_id:
                return row
        return None

    @staticmethod
    def _fetch_org_rows(table_name: str, organization_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                supabase.table(table_name)
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
                .data
                or []
            )
            if rows:
                return rows
            return (
                supabase.table(table_name)
                .select("*")
                .is_("organization_id", "null")
                .execute()
                .data
                or []
            )
        except Exception:
            return []

    @staticmethod
    def _fetch_rows(table_name: str) -> list[dict[str, Any]]:
        try:
            return supabase.table(table_name).select("*").execute().data or []
        except Exception:
            return []

    @staticmethod
    def _distribution(rows: list[dict[str, Any]], field: str, label: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(field) or "Unassigned"
            counts[str(value)] = counts.get(str(value), 0) + 1
        return [
            {label: name, "Assets": count}
            for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]

    @staticmethod
    def _ownership_score(row: dict[str, Any]) -> float:
        populated = sum(1 for field in EnterpriseOwnershipService.QUALITY_FIELDS if row.get(field))
        return EnterpriseOwnershipService._percent(populated, len(EnterpriseOwnershipService.QUALITY_FIELDS))

    @staticmethod
    def _index_rows(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
        indexed = {}
        for row in rows:
            for field in fields:
                key = EnterpriseOwnershipService._norm(row.get(field))
                if key:
                    indexed[key] = row
        return indexed

    @staticmethod
    def _pick(*rows: dict[str, Any], keys: list[str]) -> str | None:
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
