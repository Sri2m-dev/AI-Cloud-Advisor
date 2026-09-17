"""Bounded semantic capabilities over existing financial, discovery and source authorities."""

from dataclasses import asdict

from auth.authenticated_tenant import AuthenticatedTenantContext
from enterprise_copilot.policy import ALLOWED_PERSONAS
from enterprise_copilot.semantic_planner import CapabilityDescriptor, SemanticPlanError
from services.data_source_control_tower_service import DataSourceControlTowerService
from services.enterprise_spend_composition import enterprise_spend_service
from services.live_source_service import live_source_service
from services.saas_discovery_intelligence_service import SaaSDiscoveryIntelligenceService

DEFINITIONS = {
    "cloud_financials": (
        "Observed cloud spend, provider and service totals; enterprise coverage is not inferred",
        ("TOTAL", "BY_PROVIDER", "BY_SERVICE"),
        ("provider", "service"),
    ),
    "microsoft_licenses": (
        "Microsoft subscriptions and licence SKU estate; "
        "commercial cost requires separate evidence",
        ("LIST", "COUNT", "COST"),
        ("sku_id", "sku_part_number"),
    ),
    "microsoft_assignments": (
        "Microsoft assigned subscriptions by user and exact SKU part number (for example SPE_E5); "
        "multiple distinct licences per user; assigned is not actively used",
        ("LIST", "COUNT", "MULTIPLE_LICENSES", "UNUSED"),
        ("sku_id", "sku_part_number", "user_principal_name"),
    ),
    "microsoft_applications": (
        "Registered applications discovered from Microsoft Entra service principals",
        ("LIST", "COUNT"),
        ("display_name", "publisher"),
    ),
    "source_health": (
        "Connected source health and freshness, including FAILED, STALE, DISABLED and UNKNOWN",
        ("LIST", "COUNT"),
        ("provider", "health", "source_id"),
    ),
    "source_execution": (
        "Source refresh and sync history, last success and last sync timestamps and record counts; "
        "AWS is Amazon billing, Azure is Microsoft cloud",
        ("LIST", "COUNT"),
        ("provider", "source_id", "status"),
    ),
}


class GovernedSourceCapabilities:
    def __init__(self, context, *, financial=None, live=None):
        if (
            not isinstance(context, AuthenticatedTenantContext)
            or context.role not in ALLOWED_PERSONAS
        ):
            raise PermissionError("Authenticated Ask authority is required")
        self.context = context
        self.financial = financial or enterprise_spend_service()
        self.live = live

    def catalogue(self):
        return tuple(
            CapabilityDescriptor(
                key,
                label,
                "governed_sources",
                (),
                dimensions,
                operations,
                dimensions,
                False,
                False,
                self.context.role,
                "Missing/failed evidence remains UNKNOWN; "
                "assignment is not usage; no inferred cost",
                "Persisted SourceFact or execution references accompany results",
                ("result_limit",),
            )
            for key, (label, operations, dimensions) in DEFINITIONS.items()
        )

    def handlers(self):
        return {key: self._handler(key) for key in DEFINITIONS}

    def _handler(self, key):
        def execute(*, operation, parameters, dependencies, scope, constraints):
            if scope != self.context.fabric_context:
                raise PermissionError("Capability crossed tenant boundary")
            if operation not in DEFINITIONS[key][1] or constraints["grouping"]:
                raise SemanticPlanError("Unsupported governed operation")
            # Dependencies may inform the model plan, but cannot inject authority or records.
            del dependencies
            try:
                result = self._read(key, operation)
            except PermissionError:
                raise
            except Exception:
                return {
                    "capability": key,
                    "availability": "UNKNOWN",
                    "records": (),
                    "evidence_references": (),
                    "unknowns": ("Authority unavailable.",),
                }
            rows = list(result["records"])
            for condition in constraints["filters"]:
                field = condition["dimension"]
                if field not in DEFINITIONS[key][2] or condition["operator"] != "EQUALS":
                    raise SemanticPlanError("Unsupported governed filter")
                if key == "cloud_financials" and field != {
                    "BY_PROVIDER": "provider",
                    "BY_SERVICE": "service",
                }.get(operation):
                    raise SemanticPlanError("Filter is not supported by this financial operation")
                rows = [
                    row
                    for row in rows
                    if str(row.get(field, "")).casefold() == str(condition["value"]).casefold()
                ]
            if key == "microsoft_assignments" and operation == "MULTIPLE_LICENSES":
                groups = {}
                for row in rows:
                    groups.setdefault(row["user_id"], []).append(row)
                rows = [
                    {
                        "user_id": user,
                        "user_principal_name": items[0]["user_principal_name"],
                        "sku_ids": sorted({item["sku_id"] for item in items}),
                    }
                    for user, items in groups.items()
                    if len({r["sku_id"] for r in items}) > 1
                ]
            count = (
                len({row["user_id"] for row in rows})
                if (key == "microsoft_assignments")
                else len(rows)
            )
            result["count"] = count if result["availability"] == "AVAILABLE" else None
            result["records"] = tuple(rows[: parameters.get("result_limit", 25)])
            result["capability"] = key
            return result

        return execute

    def _read(self, key, operation):
        if key == "cloud_financials":
            posture = self.financial.get_financial_posture(self.context)
            evidence = self.financial.get_financial_evidence(self.context)
            if operation == "TOTAL":
                rows = ({"amount": str(posture.cloud_spend), "currency": posture.currency},)
            else:
                dimension = "provider" if operation == "BY_PROVIDER" else "service"
                rows = tuple(
                    {
                        dimension: row.get("key") or row.get("service"),
                        "amount": str(row["spend"]),
                        "currency": posture.currency,
                    }
                    for row in getattr(self.financial, f"get_spend_by_{dimension}")(self.context)
                )
            return {
                "availability": "AVAILABLE" if posture.has_data else "UNKNOWN",
                "records": rows if posture.has_data else (),
                "evidence_references": tuple(row["evidence_reference"] for row in evidence),
                "unknowns": posture.warnings,
            }
        live = self.live or live_source_service()
        if key.startswith("microsoft_"):
            snapshot = SaaSDiscoveryIntelligenceService.snapshot(
                self.context, repository=live.repository
            )
            selection = {
                "microsoft_licenses": "skus",
                "microsoft_assignments": "assignments",
                "microsoft_applications": "applications",
            }[key]
            rows = snapshot[selection]
            if selection == "assignments":
                skus = {row["sku_id"]: row["sku_part_number"] for row in snapshot["skus"]}
                rows = [
                    {
                        **row,
                        "sku_part_number": skus.get(row["sku_id"], "UNKNOWN"),
                        "actively_used": None,
                        "utilization": "UNKNOWN",
                    }
                    for row in rows
                ]
            return {
                "availability": "UNKNOWN"
                if operation in {"UNUSED", "COST"}
                else snapshot["availability"],
                "records": () if operation in {"UNUSED", "COST"} else tuple(rows),
                "evidence_references": snapshot["evidence_references"],
                "unknowns": snapshot["unknowns"],
            }
        tower = DataSourceControlTowerService(live)
        sources = tower.list_unified_sources(self.context)
        if key == "source_health":
            rows = tuple(
                {**asdict(row), "health": row.health.value, "freshness": row.freshness.value}
                for row in sources
            )
        else:
            rows = tuple(
                {
                    **asdict(run),
                    "provider": source.provider,
                    "last_sync_at": source.last_sync_at,
                    "last_success_at": source.last_success_at,
                }
                for source in sources
                for run in tower.get_execution_history(self.context, source.source_id)
            )
        known = bool(sources) and all(row.health.value != "UNKNOWN" for row in sources)
        if key == "source_execution":
            known = bool(rows)
        partial = any(row.health.value != "UNKNOWN" for row in sources)
        return {
            "availability": "AVAILABLE" if known else "PARTIAL" if partial else "UNKNOWN",
            "records": rows,
            "evidence_references": (
                tuple(row["execution_id"] for row in rows)
                if key == "source_execution"
                else tuple(row.provenance_reference for row in sources)
            ),
            "unknowns": () if known else ("Operational coverage/health is UNKNOWN.",),
        }
