"""Read-only P1 adapter over governed cloud-cost SourceFacts; owns no cost store."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.source_facts.models import FactType, LifecycleState
from data_fabric.source_facts.persistence import SQLiteSourceFactRepository


class SourceFactFinancialRepository:
    def __init__(self, repository=None):
        self.repository = repository

    def observations(self, context, start=None, end=None):
        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("Authenticated financial tenant context is required")
        repository = self.repository
        if repository is None:
            path = os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB", "").strip()
            if not path:
                return ()
            repository = SQLiteSourceFactRepository(path)
        facts = repository.list_current_facts(context.organization_id, context.tenant_id)
        selected = {}
        for fact in facts:
            if fact.fact_type != FactType.CLOUD_COST or fact.lifecycle != LifecycleState.ACTIVE:
                continue
            if (fact.organization_id, fact.tenant_id) != (
                context.organization_id,
                context.tenant_id,
            ):
                raise PermissionError("Financial source crossed tenant boundary")
            value = fact.value
            if not isinstance(value, dict):
                raise ValueError("Malformed governed cloud-cost evidence")
            try:
                first = date.fromisoformat(value["period_start"])
                last = date.fromisoformat(value["period_end"])
                amount = Decimal(str(value["amount"]))
                currency = value["currency"]
                if not amount.is_finite() or last <= first or not currency:
                    raise ValueError
                identity = tuple(
                    value[key]
                    for key in (
                        "provider",
                        "account_id",
                        "period_start",
                        "period_end",
                        "service",
                        "currency",
                    )
                )
            except (KeyError, TypeError, ValueError, ArithmeticError):
                raise ValueError("Malformed governed cloud-cost evidence") from None
            if (start and last <= start) or (end and first > end):
                continue
            if (start and first < start) or (end and last > end + timedelta(days=1)):
                raise ValueError("Cost period cannot be prorated without evidence")
            row = {
                **value,
                "amount": amount,
                "observation_id": fact.source_fact_id,
                "source_instance_id": fact.source_instance_id,
                "execution_id": fact.ingestion_run_id,
                "observed_at": fact.observed_at,
                "evidence_reference": fact.evidence_reference or fact.source_fact_id,
                "lineage": dict(fact.lineage),
                "provenance": dict(fact.provenance),
            }
            overlap = any(
                (prior[0], prior[1], prior[4], prior[5])
                == (identity[0], identity[1], identity[4], identity[5])
                and first < date.fromisoformat(prior[3])
                and date.fromisoformat(prior[2]) < last
                for prior in selected
            )
            if overlap:
                # Two authorities must be reconciled; never silently double-count them.
                raise ValueError("Overlapping cloud-cost authorities require reconciliation")
            selected[identity] = row
        rows = tuple(selected.values())
        if len({row["currency"] for row in rows}) > 1:
            raise ValueError("Mixed currencies require an explicit governed conversion")
        return rows

    def get_posture(self, context, period_start=None, period_end=None):
        rows = self.observations(context, period_start, period_end)
        if not rows:
            return None
        total = sum((row["amount"] for row in rows), Decimal(0))
        latest = max(rows, key=lambda row: row["observed_at"])
        return {
            "organization_id": context.organization_id,
            "currency": rows[0]["currency"],
            "period_start": min(row["period_start"] for row in rows),
            "period_end": max(row["period_end"] for row in rows),
            "generated_at": datetime.now(timezone.utc),
            "source_rows": len(rows),
            "persisted_facts": len(rows),
            "import_count": len({row["execution_id"] for row in rows}),
            "latest_import_id": latest["execution_id"],
            "latest_import_status": "SUCCEEDED",
            "total_ingested_spend": total,
            "cloud_spend": total,
            "resolved_spend": total,
            "unallocated_resolved_spend": total,
            "reconciled_spend": total,
            "resolved_account_count": len({row["account_id"] for row in rows}),
            "reconciliation_status": "reconciled",
            "reconciliation_variance": Decimal(0),
            "warnings": (
                "Observed cloud evidence only; enterprise coverage and business "
                "allocation are UNKNOWN. SaaS/license cost is not inferred.",
            ),
        }

    def _group(self, context, dimension, start=None, end=None):
        groups = {}
        for row in self.observations(context, start, end):
            label = row[dimension]
            group = groups.setdefault(
                label,
                {
                    "key": label,
                    "label": label,
                    "service": label,
                    "spend": Decimal(0),
                    "currency": row["currency"],
                    "observation_ids": [],
                    "evidence_references": [],
                },
            )
            group["spend"] += row["amount"]
            group["observation_ids"].append(row["observation_id"])
            group["evidence_references"].append(row["evidence_reference"])
        return tuple(groups[key] for key in sorted(groups))

    def get_spend_by_service(self, context, start=None, end=None):
        return self._group(context, "service", start, end)

    def get_spend_by_provider(self, context, start=None, end=None):
        return self._group(context, "provider", start, end)

    def get_account_posture(self, context, start=None, end=None):
        return self._group(context, "account_id", start, end)

    def get_financial_evidence(self, context):
        return self.observations(context)

    def get_import_history(self, context):
        return tuple(
            {"import_id": row["execution_id"], "evidence_reference": row["evidence_reference"]}
            for row in self.observations(context)
        )

    def get_account_classification_evidence(self, context, account_id):
        return tuple(row for row in self.observations(context) if row["account_id"] == account_id)

    def get_accounts_classification_evidence(self, context, account_ids):
        return tuple(row for row in self.observations(context) if row["account_id"] in account_ids)
