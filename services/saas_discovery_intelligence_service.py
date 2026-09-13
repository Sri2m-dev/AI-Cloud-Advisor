"""Governed SaaS and License Intelligence Service for Nexora v1.1."""

from __future__ import annotations

import json
from dataclasses import dataclass

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.source_facts.models import FactType
from services.live_source_service import live_source_service


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
    def get_license_skus(
        context: AuthenticatedTenantContext, *, repository=None
    ) -> list[LicenseSKUOverview]:
        repo = repository or live_source_service().repository
        with repo.transaction() as db:
            rows = db.execute(
                """
                SELECT value_json FROM source_facts
                WHERE organization_id=? AND tenant_id=? AND fact_type=?
                ORDER BY observed_at DESC
                """,
                (context.organization_id, context.tenant_id, FactType.CONTRACT_TERM.value),
            ).fetchall()

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
        with repo.transaction() as db:
            rows = db.execute(
                """
                SELECT value_json FROM source_facts
                WHERE organization_id=? AND tenant_id=? AND fact_type=?
                ORDER BY observed_at DESC
                """,
                (context.organization_id, context.tenant_id, FactType.LICENSE_ASSIGNMENT.value),
            ).fetchall()

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
        with repo.transaction() as db:
            rows = db.execute(
                """
                SELECT value_json FROM source_facts
                WHERE organization_id=? AND tenant_id=? AND fact_type=?
                ORDER BY observed_at DESC
                """,
                (context.organization_id, context.tenant_id, FactType.RESOURCE_IDENTITY.value),
            ).fetchall()

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
        repo = repository or live_source_service().repository
        with repo.transaction() as db:
            rows = db.execute(
                """
                SELECT payload_json FROM source_facts
                WHERE organization_id=? AND tenant_id=? AND fact_type=?
                ORDER BY observed_at DESC
                """,
                (context.organization_id, context.tenant_id, FactType.RESOURCE_IDENTITY.value),
            ).fetchall()

            apps: dict[str, DiscoveredAppOverview] = {}
            for r in rows:
                data = json.loads(r["payload_json"])
                app = data.get("application")
                if app:
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
