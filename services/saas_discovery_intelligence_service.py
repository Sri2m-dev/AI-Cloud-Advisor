"""Governed SaaS and License Intelligence Service for Nexora v1.1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.source_facts.models import FactType, LifecycleState
from services.live_source_service import LiveSourceService, live_source_service


@dataclass(frozen=True)
class LicenseSKUOverview:
    sku_id: str
    sku_part_number: str
    total_units: int
    consumed_units: int
    unassigned_units: int
    cost: str = "UNKNOWN"


@dataclass(frozen=True)
class LicenseAssignmentOverview:
    user_id: str
    user_principal_name: str
    sku_id: str
    assigned: bool
    actively_used: bool
    utilization: str = "UNKNOWN"


@dataclass(frozen=True)
class DiscoveredAppOverview:
    external_id: str
    app_id: str | None
    display_name: str
    publisher: str
    account_enabled: bool
    cost: str = "UNKNOWN"


class SaaSDiscoveryIntelligenceService:
    """Read-only governed intelligence over tenant-isolated discovered SaaS/license evidence."""

    @staticmethod
    def _values(context, repo, kind):
        LiveSourceService.authorize(context)
        return [
            {"value_json": json.dumps(fact.value)}
            for fact in repo.list_current_facts(context.organization_id, context.tenant_id)
            if fact.fact_type == kind
            and fact.source_system == "m365"
            and fact.lifecycle == LifecycleState.ACTIVE
        ]

    @staticmethod
    def snapshot(context, *, repository=None):
        LiveSourceService.authorize(context)
        repo = repository or live_source_service().repository
        live = LiveSourceService(repo)
        sources = [row for row in live.list_sources(context) if row["provider"] == "m365"]
        facts = [
            fact
            for fact in repo.list_current_facts(context.organization_id, context.tenant_id)
            if fact.source_system == "m365" and fact.lifecycle == LifecycleState.ACTIVE
        ]
        complete = bool(sources) and all(
            row["status"] == "ACTIVE" and row["sync_status"] == "SUCCEEDED" for row in sources
        )
        availability = "AVAILABLE" if complete else "PARTIAL" if facts else "UNKNOWN"
        return {
            "availability": availability,
            "skus": [
                asdict(row)
                for row in SaaSDiscoveryIntelligenceService.get_license_skus(
                    context, repository=repo
                )
            ],
            "assignments": [
                asdict(row)
                for row in SaaSDiscoveryIntelligenceService.get_license_assignments(
                    context, repository=repo
                )
            ],
            "applications": [
                asdict(row)
                for row in SaaSDiscoveryIntelligenceService.get_discovered_applications(
                    context, repository=repo
                )
            ],
            "evidence_references": tuple(fact.source_fact_id for fact in facts)
            + tuple(
                run["execution_id"]
                for source in sources
                for run in live.executions(context, source["source_id"])[:1]
            ),
            "unknowns": ("License usage/utilization and commercial cost are UNKNOWN.",)
            + (() if complete else ("Discovery coverage is incomplete or unavailable.",)),
        }

    @staticmethod
    def get_license_skus(
        context: AuthenticatedTenantContext, *, repository=None
    ) -> list[LicenseSKUOverview]:
        repo = repository or live_source_service().repository
        rows = SaaSDiscoveryIntelligenceService._values(context, repo, FactType.CONTRACT_TERM)

        skus: dict[str, LicenseSKUOverview] = {}
        for r in rows:
            data = json.loads(r["value_json"])
            sku_data = data.get("license_sku") or data
            if "sku_id" in sku_data:
                sku_id = sku_data["sku_id"]
                if sku_id not in skus:
                    skus[sku_id] = LicenseSKUOverview(
                        sku_id=sku_id,
                        sku_part_number=sku_data.get("sku_part_number", "UNKNOWN"),
                        total_units=int(sku_data.get("total_units", 0)),
                        consumed_units=int(sku_data.get("consumed_units", 0)),
                        unassigned_units=int(sku_data.get("unassigned_units", 0)),
                        cost=sku_data.get("cost", "UNKNOWN"),
                    )
        return list(skus.values())

    @staticmethod
    def get_license_assignments(
        context: AuthenticatedTenantContext, *, repository=None
    ) -> list[LicenseAssignmentOverview]:
        repo = repository or live_source_service().repository
        rows = SaaSDiscoveryIntelligenceService._values(context, repo, FactType.LICENSE_ASSIGNMENT)

        assignments: list[LicenseAssignmentOverview] = []
        seen: set[tuple[str, str]] = set()
        for r in rows:
            data = json.loads(r["value_json"])
            assign = data.get("license_assignment") or data
            if "user_id" in assign and "sku_id" in assign:
                user_id = assign["user_id"]
                sku_id = assign["sku_id"]
                if (user_id, sku_id) not in seen:
                    seen.add((user_id, sku_id))
                    assignments.append(
                        LicenseAssignmentOverview(
                            user_id=user_id,
                            user_principal_name=assign.get("user_principal_name", ""),
                            sku_id=sku_id,
                            assigned=bool(assign.get("assigned", True)),
                            actively_used=bool(assign.get("actively_used", False)),
                            utilization=assign.get("utilization", "UNKNOWN"),
                        )
                    )
        return assignments

    @staticmethod
    def get_discovered_applications(
        context: AuthenticatedTenantContext, *, repository=None
    ) -> list[DiscoveredAppOverview]:
        repo = repository or live_source_service().repository
        rows = SaaSDiscoveryIntelligenceService._values(context, repo, FactType.RESOURCE_IDENTITY)

        apps: dict[str, DiscoveredAppOverview] = {}
        for r in rows:
            data = json.loads(r["value_json"])
            app = data.get("application") or data
            if "external_id" in app and "display_name" in app and "publisher" in app:
                ext_id = app["external_id"]
                if ext_id not in apps:
                    apps[ext_id] = DiscoveredAppOverview(
                        external_id=ext_id,
                        app_id=app.get("app_id"),
                        display_name=app.get("display_name", "Unknown Application"),
                        publisher=app.get("publisher", "Unknown"),
                        account_enabled=bool(app.get("account_enabled", True)),
                        cost=app.get("cost", "UNKNOWN"),
                    )
        return list(apps.values())
