from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from classification_engine.confidence import ConfidenceDimensions, calculate_confidence
from classification_engine.models import (
    ApprovalStatus,
    ClassificationEvidence,
    ClassificationPolicy,
    InferenceStatus,
)
from classification_engine.policy import may_allocate, may_release_spend
from classification_engine.repository import (
    InMemoryClassificationRepository,
    SupabaseClassificationRepository,
)
from classification_engine.service import ClassificationService
from classification_engine.sources import collect_aws_evidence
from data_fabric.foundation import TenantContext

NOW = datetime(2026, 8, 9, tzinfo=timezone.utc)
CTX = TenantContext("org-1", "tenant-1")


def policy(**changes):
    return ClassificationPolicy(organization_id="org-1", tenant_id="tenant-1", **changes)


def evidence(field, value, *, evidence_id="e1", source="tag", reliability=0.9, tenant="tenant-1"):
    return ClassificationEvidence(
        evidence_id=evidence_id,
        organization_id="org-1",
        tenant_id=tenant,
        source_type=source,
        source_name=source,
        source_reference=evidence_id,
        observed_field=field,
        observed_value=value,
        observed_at=NOW,
        source_reliability=reliability,
        evidence_hash=f"hash-{evidence_id}",
        lineage_reference="lineage-1",
        provenance_reference="provenance-1",
    )


def classify(items=(), chosen_policy=None, repository=None):
    return ClassificationService(repository).classify_account(
        CTX,
        account_id="727482365532",
        evidence=tuple(items),
        policy=chosen_policy or policy(),
        now=NOW,
    )


def field(results, name):
    return next(result for result in results if result.field_name == name)


def test_confidence_is_deterministic_explainable_and_canonical():
    dimensions = ConfidenceDimensions(0.9, 1, 1, 1, 1)
    first = calculate_confidence(dimensions)
    assert first == calculate_confidence(dimensions)
    assert 0 <= first.score <= 1 and "reliability" in first.formula


def test_fields_are_independent_and_unknown_is_preserved():
    results = classify((evidence("business_unit", "PMJAY"),))
    assert field(results, "business_unit").inferred_value == "PMJAY"
    assert field(results, "owner").inferred_value is None
    assert field(results, "owner").confidence_score == 0
    assert field(results, "owner").inference_status is InferenceStatus.NEEDS_REVIEW


def test_corroboration_raises_confidence_without_fixed_source_score():
    result = field(
        classify(
            (
                evidence("business_unit", "PMJAY", evidence_id="tag", source="cost_allocation_tag"),
                evidence("business_unit", "PMJAY", evidence_id="ou", source="organizations_ou"),
            )
        ),
        "business_unit",
    )
    assert result.confidence_score > 0.9
    assert result.inference_status is InferenceStatus.RESOLVED_INFERRED
    assert result.approval_status is ApprovalStatus.NEEDS_APPROVAL


def test_conflicting_tag_and_ou_never_choose_silently():
    result = field(
        classify(
            (
                evidence("business_unit", "PMJAY", evidence_id="tag"),
                evidence("business_unit", "Finance", evidence_id="ou", source="organizations_ou"),
            )
        ),
        "business_unit",
    )
    assert result.conflict is True
    assert set(result.candidate_values) == {"PMJAY", "Finance"}
    assert result.inference_status is InferenceStatus.NEEDS_REVIEW
    assert "conflicting" in result.review_reason


def test_reinference_is_idempotent_and_evidence_change_versions():
    repository = InMemoryClassificationRepository()
    first = field(
        classify((evidence("environment", "Production"),), repository=repository), "environment"
    )
    replay = field(
        classify((evidence("environment", "Production"),), repository=repository), "environment"
    )
    changed = field(
        classify(
            (evidence("environment", "NonProduction", evidence_id="e2"),), repository=repository
        ),
        "environment",
    )
    assert replay.id == first.id
    assert changed.version == 2
    assert len(repository.history(CTX, "cloud_account", "727482365532", "environment")) == 2


def test_approved_value_is_protected_from_later_inference():
    repository = InMemoryClassificationRepository()
    current = field(
        classify((evidence("cost_center", "CC-1"),), repository=repository), "cost_center"
    )
    approved = repository.approve(
        CTX, current.id, actor="owner@example.com", reason="Owner approval"
    )
    proposed = field(
        classify((evidence("cost_center", "CC-2", evidence_id="e2"),), repository=repository),
        "cost_center",
    )
    assert approved.inferred_value == "CC-1"
    assert proposed.inference_status is InferenceStatus.NEEDS_REVIEW
    assert "protected approved" in proposed.review_reason


def test_cross_tenant_evidence_and_policy_are_rejected():
    with pytest.raises(Exception, match="tenant boundary"):
        classify((evidence("owner", "x", tenant="other"),))
    with pytest.raises(PermissionError, match="cross-tenant"):
        classify(chosen_policy=replace(policy(), tenant_id="other"))


def test_auto_approval_is_disabled_by_default_and_requires_authority():
    result = field(
        classify(
            (
                evidence("application", "Nexora", evidence_id="a"),
                evidence("application", "Nexora", evidence_id="b", source="cost_category"),
            )
        ),
        "application",
    )
    assert result.approval_status is ApprovalStatus.NEEDS_APPROVAL
    with pytest.raises(ValueError, match="authority"):
        policy(auto_approval_enabled=True)


def test_authorized_auto_approval_and_separate_financial_policies():
    approved_policy = policy(
        auto_approval_enabled=True,
        approved_by="tenant-owner",
        approved_at=NOW,
        allow_provisional_spend_release=True,
    )
    result = field(
        classify(
            (
                evidence("application", "Nexora", evidence_id="a"),
                evidence("application", "Nexora", evidence_id="b", source="cost_category"),
            ),
            approved_policy,
        ),
        "application",
    )
    assert result.approval_status is ApprovalStatus.AUTO_APPROVED
    assert may_release_spend(InferenceStatus.RESOLVED_INFERRED, approved_policy)
    assert not may_allocate(InferenceStatus.RESOLVED_INFERRED, approved_policy)


def test_default_policy_keeps_inferred_spend_quarantined_and_unallocated():
    assert not may_release_spend(InferenceStatus.RESOLVED_INFERRED, policy())
    assert not may_allocate(InferenceStatus.RESOLVED_INFERRED, policy())


def test_aws_sources_are_extracted_in_governed_priority_order():
    items = collect_aws_evidence(
        organization_id="org-1",
        tenant_id="tenant-1",
        account_id="727482365532",
        observed_at=NOW,
        metadata={
            "cost_allocation_tags": {"BusinessUnit": "PMJAY", "CostCenter": "CC-1045"},
            "account_alias": "NHA-PMJAY-PROD",
            "organizations_ou": "NHA/PMJAY",
        },
    )
    assert items[0].source_type == "cost_allocation_tags"
    assert any(
        item.observed_field == "environment" and item.observed_value == "Production"
        for item in items
    )
    assert sum(item.observed_value == "PMJAY" for item in items) == 3


def test_real_account_727482365532_sparse_evidence_remains_governed():
    def live_item(field_name, value, evidence_id, coverage):
        item = evidence(
            field_name,
            value,
            evidence_id=evidence_id,
            source="account_alias" if field_name == "account_name" else "resource_tags",
            reliability=0.8,
        )
        return replace(item, metadata={"coverage": coverage})

    results = classify(
        (
            live_item("account_name", "HG_AWS01", "account-name", 1),
            live_item("application", "KordiaSoc", "product", 8 / 14455),
            live_item("owner", "Rob Wright", "owner-1", 104 / 14455),
            live_item("owner", "security@humm-group.com", "owner-2", 8 / 14455),
        )
    )
    assert field(results, "account_name").inference_status is InferenceStatus.RESOLVED_INFERRED
    assert field(results, "account_name").confidence_score == 0.84
    assert field(results, "application").inference_status is InferenceStatus.NEEDS_REVIEW
    assert field(results, "owner").conflict is True
    assert field(results, "business_unit").inferred_value is None


def test_migration_is_additive_tenant_scoped_and_never_mutates_cur():
    sql = (
        Path("supabase/migrations/202608090001_p42_enterprise_classification.sql")
        .read_text()
        .lower()
    )
    assert "classification_evidence_link" in sql and "evidence_id text" in sql
    assert "enable row level security" in sql
    assert "auto_approval_enabled boolean not null default false" in sql
    assert "drop table" not in sql and "delete from" not in sql
    assert "update public.cloud_cost_fact" not in sql


def test_supabase_repository_uses_tenant_validating_inference_rpc():
    class Response:
        data = {"id": "result-1", "version": 3}

    class Client:
        def rpc(self, name, payload):
            self.name, self.payload = name, payload
            return self

        def execute(self):
            return Response()

    client = Client()
    inferred = field(classify((evidence("account_name", "HG_AWS01"),)), "account_name")
    saved = SupabaseClassificationRepository(client).save(CTX, inferred)
    assert client.name == "p42_save_inferred_classification"
    assert client.payload["requested_organization_id"] == CTX.organization_id
    assert saved.version == 3


def test_persistence_rpc_denies_approval_and_protects_approved_values():
    sql = (
        Path("supabase/migrations/202608090004_p42_inference_persistence_rpc.sql")
        .read_text()
        .lower()
    )
    assert "inference service has no approval authority" in sql
    assert "new evidence conflicts with protected approved value" in sql
    assert "pvt003c1_can_read_organization" in sql
