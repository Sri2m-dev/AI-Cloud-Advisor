from __future__ import annotations

import json
import sqlite3
from decimal import Decimal

from .engine import aggregate_portfolio
from .governance import GovernedOptimizationRepository
from .models import OpportunityState


class CanonicalOptimizationRepository:
    """Durable canonical opportunity projection for Data Fabric/KG consumers."""

    def __init__(self, database):
        self.database = str(database)
        with sqlite3.connect(self.database) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS canonical_optimization_opportunities (
                opportunity_id TEXT NOT NULL, version INTEGER NOT NULL,
                organization_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL, prospect_id TEXT NOT NULL, analysis_id TEXT NOT NULL,
                state TEXT NOT NULL, currency TEXT, potential_savings TEXT, realized_savings TEXT,
                affected_entity TEXT NOT NULL, fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY(opportunity_id, version))""")

    def publish(self, item, context):
        if item.organization_id != context.organization_id or item.tenant_id != context.tenant_id:
            raise PermissionError("cross-tenant opportunity publication rejected")
        payload = GovernedOptimizationRepository._payload(item)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO canonical_optimization_opportunities "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item.opportunity_id,
                    item.version,
                    item.organization_id,
                    item.tenant_id,
                    item.prospect_id,
                    item.analysis_id,
                    item.state.value,
                    item.currency,
                    str(item.potential_savings) if item.potential_savings is not None else None,
                    str(item.realized_savings) if item.realized_savings is not None else None,
                    item.affected_entity,
                    item.fingerprint,
                    json.dumps(payload, sort_keys=True),
                ),
            )
        return item

    def list(self, context):
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute(
                "SELECT payload_json FROM canonical_optimization_opportunities "
                "WHERE organization_id=? AND tenant_id=? "
                "ORDER BY opportunity_id, version",
                (context.organization_id, context.tenant_id),
            ).fetchall()
        return tuple(
            GovernedOptimizationRepository._opportunity(json.loads(row[0])) for row in rows
        )

    def relationships(self, context):
        relationships = []
        for item in self.list(context):
            relationships.append(
                (item.affected_entity, "HAS_OPTIMIZATION_OPPORTUNITY", item.opportunity_id)
            )
            relationships.extend(
                (item.opportunity_id, "SUPPORTED_BY", ref) for ref in item.evidence_references
            )
        return tuple(relationships)

    def savings_summary(self, context):
        items = self.list(context)
        active = tuple(
            item
            for item in items
            if item.state
            not in {
                OpportunityState.SUPERSEDED,
                OpportunityState.REJECTED,
                OpportunityState.BLOCKED,
                OpportunityState.REVISION_REQUIRED,
            }
        )
        portfolio = aggregate_portfolio(active)
        potential = dict(portfolio.totals_by_currency)
        approved: dict[str, Decimal] = {}
        implemented: dict[str, Decimal] = {}
        realized: dict[str, Decimal] = {}
        selected = set(portfolio.selected_opportunity_ids)
        for item in active:
            if item.opportunity_id not in selected:
                continue
            if (
                item.state
                in {
                    OpportunityState.APPROVED,
                    OpportunityState.IMPLEMENTING,
                    OpportunityState.IMPLEMENTED,
                    OpportunityState.VERIFYING,
                    OpportunityState.REALIZED,
                    OpportunityState.PARTIALLY_REALIZED,
                    OpportunityState.NOT_REALIZED,
                }
                and item.potential_savings is not None
            ):
                approved[item.currency] = (
                    approved.get(item.currency, Decimal("0")) + item.potential_savings
                )
            if (
                item.state
                in {
                    OpportunityState.IMPLEMENTED,
                    OpportunityState.VERIFYING,
                    OpportunityState.REALIZED,
                    OpportunityState.PARTIALLY_REALIZED,
                    OpportunityState.NOT_REALIZED,
                }
                and item.potential_savings is not None
            ):
                implemented[item.currency] = (
                    implemented.get(item.currency, Decimal("0")) + item.potential_savings
                )
            if item.realized_savings is not None:
                realized[item.currency] = (
                    realized.get(item.currency, Decimal("0")) + item.realized_savings
                )
        return {
            "opportunity_count": len(items),
            "potential_by_currency": tuple(sorted(potential.items())),
            "approved_by_currency": tuple(sorted(approved.items())),
            "implemented_by_currency": tuple(sorted(implemented.items())),
            "realized_by_currency": tuple(sorted(realized.items())),
            "excluded_overlap_ids": portfolio.excluded_overlap_ids,
        }
