"""Publish certified Golden Demo cloud evidence into the existing SourceFact store."""

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from decimal import Decimal
from threading import RLock

from auth.authenticated_tenant import AuthenticatedTenantContext
from data_fabric.source_facts.models import (
    FactType,
    Freshness,
    LifecycleState,
    SourceFactInput,
    SourceInstance,
)
from data_fabric.source_facts.persistence import SQLiteSourceFactRepository
from data_fabric.source_facts.service import SourceFactService
from enterprise_intelligence.search import FINANCIAL_ROLES
from services.demo_tenant_service import DEMO_ORGANIZATION_ID, load_demo_tenant

_LOCK = RLock()
SOURCE_ID = "golden-demo:certified-cloud-financials"
EVIDENCE_REFERENCE = "data/demo/nexora_global_retail.json#/metrics/annual_cloud_spend"


def bootstrap_demo_financial_sourcefacts(context):
    """No fallback tenant, database path, billing dates, currency, or allocation."""
    if (
        not isinstance(context, AuthenticatedTenantContext)
        or context.organization_id != DEMO_ORGANIZATION_ID
        or context.tenant_id != DEMO_ORGANIZATION_ID
        or context.role not in FINANCIAL_ROLES
    ):
        raise PermissionError("Certified demo financial publication scope is required")
    payload = load_demo_tenant(context.organization_id)
    database = os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB", "").strip()
    if not database:
        return {"status": "UNKNOWN", "reason": "Canonical SourceFact database is not configured"}
    amount = Decimal(str(payload["metrics"]["annual_cloud_spend"]))
    if not amount.is_finite() or amount < 0:
        raise ValueError("Invalid certified cloud spend")
    snapshot = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    observed = datetime.fromisoformat(payload["as_of"].replace("Z", "+00:00"))
    record = SourceFactInput(
        source_record_id="metrics.annual_cloud_spend",
        fact_type=FactType.CLOUD_COST,
        subject_reference=f"{context.organization_id}:cloud_spend",
        predicate="reported_cloud_spend",
        value={
            "aggregation_level": "enterprise_cloud_total",
            "amount": str(amount),
            "currency": payload.get("currency") or "UNKNOWN",
            "period_label": "annual; exact dates UNKNOWN",
            "period_start": None,
            "period_end": None,
            "provider": None,
            "service": None,
            "account_id": None,
            "source_snapshot": snapshot,
        },
        observed_at=observed,
        freshness=Freshness.UNKNOWN,
        evidence_reference=EVIDENCE_REFERENCE,
        lineage={
            "source": payload["source"],
            "json_pointer": "/metrics/annual_cloud_spend",
            "dataset_sha256": snapshot,
        },
        provenance={
            "classification": payload["classification"],
            "as_of": payload["as_of"],
            "dataset_organization_id": payload["organization_id"],
            "coverage": "Reported cloud total only; no certified dimensional allocation",
        },
    )
    run_id = f"golden-demo:financial:{snapshot}"
    instance = SourceInstance(
        SOURCE_ID,
        context.organization_id,
        context.tenant_id,
        "synthetic_demonstration_evidence",
        payload["source"],
        "certified_demo",
        "1",
        "data/demo/nexora_global_retail.json",
        created_at=observed,
        updated_at=observed,
    )
    with _LOCK:
        repository = SQLiteSourceFactRepository(database)
        current = tuple(
            fact
            for fact in repository.list_current_facts(
                context.organization_id,
                context.tenant_id,
            )
            if fact.source_instance_id == SOURCE_ID
        )
        if any(fact.lifecycle is not LifecycleState.ACTIVE for fact in current):
            return {"status": "UNKNOWN", "reason": "Existing demo evidence is not active"}
        if repository.run_counts(context.organization_id, context.tenant_id, SOURCE_ID):
            if not repository.instance_enabled(
                context.organization_id, context.tenant_id, SOURCE_ID
            ):
                raise PermissionError("Disabled demo financial authority cannot be reactivated")
            if len(current) == 1 and current[0].value == record.value:
                return {
                    "status": "UNCHANGED",
                    "run_id": current[0].ingestion_run_id,
                    "source_fact_id": current[0].source_fact_id,
                }
        service = SourceFactService(context.fabric_context, repository)
        service.register(instance)
        try:
            result = service.publish(instance, (record,), run_id=run_id)
        except sqlite3.IntegrityError:
            # A concurrent initialization may have committed the same deterministic run.
            current = tuple(
                fact
                for fact in repository.list_current_facts(
                    context.organization_id,
                    context.tenant_id,
                )
                if fact.source_instance_id == SOURCE_ID and fact.value == record.value
            )
            if len(current) != 1:
                raise
            return {
                "status": "UNCHANGED",
                "run_id": run_id,
                "source_fact_id": current[0].source_fact_id,
            }
        return {
            "status": result.status.value,
            "run_id": run_id,
            "source_fact_ids": tuple(fact.source_fact_id for fact in result.facts),
        }
