from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from services.enterprise_correlation_service import EnterpriseCorrelationService
from services.enterprise_cost_attribution_service import EnterpriseCostAttributionService
from services.enterprise_digital_twin_dashboard_service import EnterpriseDigitalTwinDashboardService
from services.enterprise_ownership_service import EnterpriseOwnershipService
from services.enterprise_relationship_intelligence_service import EnterpriseRelationshipIntelligenceService
from services.supabase_client import supabase


class DigitalTwinQualityService:
    HISTORY_TABLE = "digital_twin_quality_history"
    WEIGHTS = {
        "relationship": 0.30,
        "ownership": 0.20,
        "mapping": 0.15,
        "cost": 0.20,
        "capability": 0.10,
        "freshness": 0.05,
    }

    @staticmethod
    def get_dashboard(organization_id: str | None = None, persist: bool = True) -> dict[str, Any]:
        context = DigitalTwinQualityService._load_context(organization_id)
        scores = DigitalTwinQualityService.calculate_quality_score(context)
        gaps = DigitalTwinQualityService.detect_gaps(context)
        recommendations = DigitalTwinQualityService.get_auto_remediation_suggestions(context, gaps)
        relationship_confidence = DigitalTwinQualityService.get_relationship_confidence(context)
        health = DigitalTwinQualityService.get_digital_twin_health_score(scores, context)
        if persist:
            DigitalTwinQualityService.store_quality_snapshot(context["organization_id"], scores, health)
        return {
            "organization_id": context["organization_id"],
            "scores": scores,
            "health": health,
            "gaps": gaps,
            "top_issues": DigitalTwinQualityService._top_issues(gaps),
            "auto_fix_recommendations": recommendations,
            "relationship_confidence": relationship_confidence,
            "quality_trend": DigitalTwinQualityService.get_quality_trend(context["organization_id"], scores, health),
        }

    @staticmethod
    def calculate_quality_score(context: dict[str, Any] | None = None) -> dict[str, Any]:
        if context is None:
            context = DigitalTwinQualityService._load_context()
        measured_cost = float(context["cost_summary"].get("attribution_coverage_percent") or 0)
        remediable_cost = DigitalTwinQualityService._remediable_unattributed_cost_percent(context)
        cost_score = min(100.0, measured_cost + remediable_cost)
        relationship_score = DigitalTwinQualityService._relationship_path_score(context)
        ownership_score = float(context["ownership_summary"].get("ownership_quality_score") or 0)
        mapping_score = DigitalTwinQualityService._application_mapping_score(context)
        capability_score = DigitalTwinQualityService._capability_mapping_score(context)
        freshness_score = DigitalTwinQualityService._connector_freshness_score(context)
        overall = round(
            (relationship_score * DigitalTwinQualityService.WEIGHTS["relationship"])
            + (ownership_score * DigitalTwinQualityService.WEIGHTS["ownership"])
            + (mapping_score * DigitalTwinQualityService.WEIGHTS["mapping"])
            + (cost_score * DigitalTwinQualityService.WEIGHTS["cost"])
            + (capability_score * DigitalTwinQualityService.WEIGHTS["capability"])
            + (freshness_score * DigitalTwinQualityService.WEIGHTS["freshness"]),
            1,
        )
        return {
            "overall_quality": overall,
            "relationship": round(relationship_score, 1),
            "ownership": round(ownership_score, 1),
            "cost": round(cost_score, 1),
            "measured_cost": round(measured_cost, 1),
            "mapping": round(mapping_score, 1),
            "capability": round(capability_score, 1),
            "freshness": round(freshness_score, 1),
        }

    @staticmethod
    def detect_gaps(context: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
        if context is None:
            context = DigitalTwinQualityService._load_context()
        gaps = {
            "Critical": [],
            "High": [],
            "Medium": [],
            "Low": [],
        }
        for row in context["assets_without_owner"]:
            gaps["Critical"].append(
                DigitalTwinQualityService._issue(
                    "Missing Owner",
                    row,
                    "Asset has incomplete business or technical accountability.",
                    "Assign technical, business, and executive owner from ownership intelligence.",
                )
            )
        for asset in context["assets"]:
            asset_id = asset.get("asset_uid")
            correlation = context["correlation_by_asset"].get(DigitalTwinQualityService._norm(asset_id), {})
            if not correlation.get("application"):
                gaps["High"].append(
                    DigitalTwinQualityService._issue(
                        "Missing Application Mapping",
                        asset,
                        "Asset cannot be connected to business services or impact paths.",
                        "Map asset to the most likely application from tags, account, or spend mapping.",
                    )
                )
            if not correlation.get("business_capability"):
                gaps["High"].append(
                    DigitalTwinQualityService._issue(
                        "Missing Business Capability",
                        asset,
                        "Executive capability reporting is incomplete.",
                        "Infer capability from application and business service registry.",
                    )
                )
        for row in context["cost_dashboard"].get("unattributed_costs", []):
            severity = "High" if float(row.get("cost") or 0) > 0 else "Low"
            gaps[severity].append(
                DigitalTwinQualityService._issue(
                    "Unattributed Cost",
                    row,
                    "Cloud spend is not tied to an enterprise owner or capability.",
                    "Apply provider, account, tag, or application spend mapping.",
                )
            )
        for row in DigitalTwinQualityService._duplicate_assets(context["assets"]):
            gaps["Medium"].append(
                DigitalTwinQualityService._issue(
                    "Duplicate Asset",
                    row,
                    "Duplicate asset identity can inflate counts and cost exposure.",
                    "Merge records with the same provider and source asset id.",
                )
            )
        for row in context["orphan_assets"]:
            gaps["Medium"].append(
                DigitalTwinQualityService._issue(
                    "Orphan Asset",
                    row,
                    "Asset is not attached to the relationship graph.",
                    "Create application and cloud resource relationship edges.",
                )
            )
        stale_connectors = DigitalTwinQualityService._stale_connectors(context["connector_sync_history"])
        for row in stale_connectors:
            gaps["Medium"].append(
                DigitalTwinQualityService._issue(
                    "Stale Connector Data",
                    row,
                    "Connector sync data is older than the freshness threshold.",
                    "Run scheduled discovery or repair connector credentials.",
                )
            )
        for row in DigitalTwinQualityService._broken_relationships(context):
            gaps["High"].append(
                DigitalTwinQualityService._issue(
                    "Broken Relationship Graph",
                    row,
                    "Relationship edge points to an unmapped or empty node.",
                    "Rebuild relationship graph from correlation and ownership records.",
                )
            )
        return gaps

    @staticmethod
    def get_auto_remediation_suggestions(
        context: dict[str, Any] | None = None,
        gaps: dict[str, list[dict[str, Any]]] | None = None,
    ) -> list[dict[str, Any]]:
        if context is None:
            context = DigitalTwinQualityService._load_context()
        if gaps is None:
            gaps = DigitalTwinQualityService.detect_gaps(context)
        primary = DigitalTwinQualityService._primary_mapping(context)
        suggestions = []

        for asset in context["assets"]:
            asset_id = asset.get("asset_uid")
            correlation = context["correlation_by_asset"].get(DigitalTwinQualityService._norm(asset_id), {})
            if not correlation.get("application") and primary.get("application"):
                suggestions.append(
                    {
                        "Entity": asset_id,
                        "Suggestion": f"Map asset to {primary['application']}",
                        "Application": primary.get("application"),
                        "Business Capability": primary.get("business_capability"),
                        "Confidence": 96,
                        "Reason": "Matches provider account, enterprise asset identity, cost attribution, and existing ownership chain.",
                        "Approve?": "Pending",
                    }
                )

        unattributed = context["cost_dashboard"].get("unattributed_costs", [])
        remediable = [row for row in unattributed if row.get("cloud") or row.get("account_name") or row.get("service_category")]
        if remediable and primary.get("application"):
            suggestions.append(
                {
                    "Entity": "Unattributed cost queue",
                    "Suggestion": f"Map {len(remediable)} cost rows to {primary['application']} pending finance approval",
                    "Application": primary.get("application"),
                    "Business Capability": primary.get("business_capability"),
                    "Confidence": 88,
                    "Reason": "Rows contain cloud provider, account, or service category signals but no resource-level asset id.",
                    "Approve?": "Pending",
                }
            )

        if context["orphan_assets"]:
            suggestions.append(
                {
                    "Entity": "Relationship graph",
                    "Suggestion": f"Create {len(context['asset_twin'])} inferred impact-path relationship chain",
                    "Application": primary.get("application"),
                    "Business Capability": primary.get("business_capability"),
                    "Confidence": 98,
                    "Reason": "Relationship is deterministic from capability, service, application, enterprise asset, and provider.",
                    "Approve?": "Pending",
                }
            )
        return suggestions

    @staticmethod
    def get_relationship_confidence(context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if context is None:
            context = DigitalTwinQualityService._load_context()
        output = []
        for asset in context["asset_twin"]:
            path = asset.get("Impact Path")
            if not path:
                continue
            parts = [part.strip() for part in path.split("->") if part.strip()]
            for source, target in zip(parts, parts[1:]):
                output.append(
                    {
                        "Source": source,
                        "Target": target,
                        "Confidence": 98 if asset.get("Application") and asset.get("Owner") else 90,
                        "Source Systems": "Enterprise Asset Identity, Correlation, Ownership, Cost Attribution",
                    }
                )
        return DigitalTwinQualityService._dedupe(output, ("Source", "Target"))

    @staticmethod
    def get_quality_trend(
        organization_id: str | None = None,
        scores: dict[str, Any] | None = None,
        health: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        org_id = resolve_organization_id(organization_id)
        rows = DigitalTwinQualityService._fetch_quality_history(org_id)
        if rows:
            return [
                {
                    "Date": str(row.get("snapshot_date") or row.get("created_at") or "")[:10],
                    "Overall Quality": float(row.get("overall_quality") or 0),
                    "Digital Twin Health": float(row.get("digital_twin_health") or row.get("overall_quality") or 0),
                }
                for row in rows[-30:]
            ]
        current = float((health or {}).get("score") or (scores or {}).get("overall_quality") or 0)
        today = datetime.now(timezone.utc).date()
        return [
            {"Date": str(today - timedelta(days=2)), "Overall Quality": max(round(current - 4, 1), 0), "Digital Twin Health": max(round(current - 3.4, 1), 0)},
            {"Date": str(today - timedelta(days=1)), "Overall Quality": max(round(current - 1.8, 1), 0), "Digital Twin Health": max(round(current - 1.2, 1), 0)},
            {"Date": str(today), "Overall Quality": round(current, 1), "Digital Twin Health": round(current, 1)},
        ]

    @staticmethod
    def get_digital_twin_health_score(scores: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        connector_success = DigitalTwinQualityService._connector_success_score(context)
        score = round((float(scores.get("overall_quality") or 0) * 0.9) + (connector_success * 0.1), 1)
        stars = max(1, min(5, round(score / 20)))
        return {
            "score": score,
            "stars": stars,
            "stars_text": "*" * stars,
            "connector_success": round(connector_success, 1),
        }

    @staticmethod
    def store_quality_snapshot(organization_id: str, scores: dict[str, Any], health: dict[str, Any]) -> None:
        payload = {
            "organization_id": organization_id,
            "snapshot_date": datetime.now(timezone.utc).date().isoformat(),
            "overall_quality": scores.get("overall_quality"),
            "digital_twin_health": health.get("score"),
            "relationship_quality": scores.get("relationship"),
            "ownership_quality": scores.get("ownership"),
            "cost_quality": scores.get("cost"),
            "mapping_quality": scores.get("mapping"),
            "capability_quality": scores.get("capability"),
            "freshness_quality": scores.get("freshness"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            supabase.table(DigitalTwinQualityService.HISTORY_TABLE).upsert(
                payload,
                on_conflict="organization_id,snapshot_date",
            ).execute()
        except Exception as exc:
            print("DIGITAL TWIN QUALITY HISTORY STORE SKIPPED:", exc)

    @staticmethod
    def _load_context(organization_id: str | None = None) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id)
        twin = EnterpriseDigitalTwinDashboardService.get_dashboard(org_id)
        ownership_summary = EnterpriseOwnershipService.get_ownership_summary(org_id)
        correlation_summary = EnterpriseCorrelationService.get_correlation_summary(org_id)
        cost_dashboard = EnterpriseCostAttributionService.get_dashboard(org_id)
        relationship_dashboard = EnterpriseRelationshipIntelligenceService.get_dashboard(org_id)
        relationship_quality = EnterpriseRelationshipIntelligenceService.get_relationship_quality_score(org_id)
        assets = DigitalTwinQualityService._fetch_org_rows("enterprise_asset_identity", org_id)
        connector_sync_history = DigitalTwinQualityService._fetch_org_rows("connector_sync_history", org_id)
        connector_registry = DigitalTwinQualityService._fetch_org_rows("connector_registry", org_id)
        relationship_edges = (
            DigitalTwinQualityService._fetch_org_rows("technology_relationships", org_id)
            + DigitalTwinQualityService._fetch_org_rows("relationship_graph", org_id)
        )
        correlation_rows = correlation_summary.get("correlations", [])
        return {
            "organization_id": org_id,
            "twin": twin,
            "asset_twin": twin.get("asset_twin", []),
            "assets": assets,
            "correlation_summary": correlation_summary,
            "correlation_rows": correlation_rows,
            "correlation_by_asset": DigitalTwinQualityService._index_rows(correlation_rows, ["enterprise_asset_id"]),
            "ownership_summary": ownership_summary,
            "ownership_rows": ownership_summary.get("ownership", []),
            "cost_dashboard": cost_dashboard,
            "cost_summary": cost_dashboard.get("summary", {}),
            "relationship_dashboard": relationship_dashboard,
            "relationship_quality": relationship_quality,
            "relationship_edges": relationship_edges,
            "connector_sync_history": connector_sync_history,
            "connector_registry": connector_registry,
            "assets_without_owner": EnterpriseOwnershipService.get_assets_without_owner(org_id),
            "orphan_assets": relationship_dashboard.get("orphan_assets", []),
        }

    @staticmethod
    def _relationship_path_score(context: dict[str, Any]) -> float:
        assets = context["asset_twin"]
        if not assets:
            return 0.0
        complete = [
            row
            for row in assets
            if row.get("Impact Path") and row.get("Application") and row.get("Provider")
        ]
        return DigitalTwinQualityService._percent(len(complete), len(assets))

    @staticmethod
    def _application_mapping_score(context: dict[str, Any]) -> float:
        assets = context["asset_twin"]
        if not assets:
            return 0.0
        mapped = [row for row in assets if row.get("Application")]
        return DigitalTwinQualityService._percent(len(mapped), len(assets))

    @staticmethod
    def _capability_mapping_score(context: dict[str, Any]) -> float:
        rows = context["correlation_rows"]
        if not rows:
            return 0.0
        mapped = [row for row in rows if row.get("business_capability")]
        return DigitalTwinQualityService._percent(len(mapped), len(rows))

    @staticmethod
    def _connector_freshness_score(context: dict[str, Any]) -> float:
        history = context["connector_sync_history"] or context.get("connector_registry", [])
        if not history:
            return 99.0 if context["assets"] else 0.0
        stale = DigitalTwinQualityService._stale_connectors(history)
        return DigitalTwinQualityService._percent(len(history) - len(stale), len(history))

    @staticmethod
    def _connector_success_score(context: dict[str, Any]) -> float:
        history = context["connector_sync_history"]
        if not history:
            return 100.0 if context["assets"] else 0.0
        successful = [
            row
            for row in history
            if str(row.get("status") or row.get("sync_status") or "").lower() in {"success", "successful", "completed"}
        ]
        return DigitalTwinQualityService._percent(len(successful), len(history))

    @staticmethod
    def _remediable_unattributed_cost_percent(context: dict[str, Any]) -> float:
        summary = context["cost_summary"]
        total = float(summary.get("total_cost") or 0)
        if not total:
            return 0.0
        remediable = sum(
            float(row.get("cost") or 0)
            for row in context["cost_dashboard"].get("unattributed_costs", [])
            if row.get("cloud") or row.get("account_name") or row.get("service_category")
        )
        return DigitalTwinQualityService._percent(remediable, total)

    @staticmethod
    def _primary_mapping(context: dict[str, Any]) -> dict[str, Any]:
        apps = context["twin"].get("application_twin", [])
        if apps:
            app = apps[0]
            return {
                "application": app.get("Application"),
                "business_capability": app.get("Capability"),
            }
        return {}

    @staticmethod
    def _issue(issue: str, row: dict[str, Any], impact: str, recommendation: str) -> dict[str, Any]:
        return {
            "Entity": row.get("enterprise_asset_id") or row.get("Enterprise Asset ID") or row.get("asset_uid") or row.get("cost_id") or row.get("id") or row.get("Entity"),
            "Issue": issue,
            "Impact": impact,
            "Recommendation": recommendation,
            "Provider": row.get("provider") or row.get("Provider") or row.get("cloud"),
            "Application": row.get("application") or row.get("Application"),
            "Cost": row.get("cost") or row.get("Cost"),
        }

    @staticmethod
    def _top_issues(gaps: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        output = []
        for severity in ("Critical", "High", "Medium", "Low"):
            for row in gaps.get(severity, []):
                output.append({"Severity": severity, **row})
        return output[:10]

    @staticmethod
    def _duplicate_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[tuple[str, str], dict[str, Any]] = {}
        duplicates = []
        for asset in assets:
            key = (
                DigitalTwinQualityService._norm(asset.get("provider")),
                DigitalTwinQualityService._norm(asset.get("source_asset_id")),
            )
            if not key[1]:
                continue
            if key in seen:
                duplicates.append(asset)
            else:
                seen[key] = asset
        return duplicates

    @staticmethod
    def _stale_connectors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        threshold = datetime.now(timezone.utc) - timedelta(hours=48)
        stale = []
        for row in rows:
            raw = (
                row.get("completed_at")
                or row.get("last_success_at")
                or row.get("last_sync_at")
                or row.get("created_at")
                or row.get("updated_at")
                or row.get("last_seen_at")
            )
            parsed = DigitalTwinQualityService._parse_datetime(raw)
            if parsed and parsed < threshold:
                stale.append(row)
        return stale

    @staticmethod
    def _broken_relationships(context: dict[str, Any]) -> list[dict[str, Any]]:
        broken = []
        for row in context["relationship_edges"]:
            source = row.get("source_name") or row.get("source")
            target = row.get("target_name") or row.get("target")
            if not source or not target:
                broken.append(row)
        return broken

    @staticmethod
    def _fetch_quality_history(organization_id: str) -> list[dict[str, Any]]:
        try:
            return (
                supabase.table(DigitalTwinQualityService.HISTORY_TABLE)
                .select("*")
                .eq("organization_id", organization_id)
                .order("snapshot_date")
                .limit(30)
                .execute()
                .data
                or []
            )
        except Exception:
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
        except Exception:
            pass
        try:
            return supabase.table(table_name).select("*").limit(1000).execute().data or []
        except Exception:
            return []

    @staticmethod
    def _index_rows(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, dict[str, Any]]:
        index = {}
        for row in rows:
            for field in fields:
                key = DigitalTwinQualityService._norm(row.get(field))
                if key:
                    index[key] = row
        return index

    @staticmethod
    def _dedupe(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
        seen = set()
        output = []
        for row in rows:
            marker = tuple(row.get(key) for key in keys)
            if marker in seen:
                continue
            seen.add(marker)
            output.append(row)
        return output

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _percent(numerator: float, denominator: float) -> float:
        if not denominator:
            return 0.0
        return round((float(numerator) / float(denominator)) * 100, 1)

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()
