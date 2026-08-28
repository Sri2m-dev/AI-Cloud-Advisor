from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data_fabric.contracts import EntityType
from universal_evidence.contracts import ConfirmationState
from universal_evidence.durable_runtime import DurableRuntimeComposition
from universal_evidence.governance import (
    ActorType,
    ConfirmationActor,
    DecisionScope,
    MappingDecision,
    MappingDecisionState,
)
from universal_evidence.governance.models import GovernanceDecisionProvenance
from universal_evidence.governance.service import ConfirmationService
from universal_evidence.persistence import LifecycleScope
from universal_evidence.pilot.reconciliation import SourceIdentityBinding


def _decision(scope, decision_id="decision-1", state=MappingDecisionState.CONFIRMED):
    actor = ConfirmationActor("human-1", "human-1", "super_admin", ActorType.HUMAN)
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    return MappingDecision(
        decision_id,
        f"fp-{decision_id}",
        scope,
        "technology.service",
        state,
        ConfirmationState.CONFIRMED
        if state is MappingDecisionState.CONFIRMED
        else ConfirmationState.REJECTED,
        actor,
        now,
        "restart certification",
        (("technology.service", 0.99),),
        GovernanceDecisionProvenance(
            "discovery-1",
            "semantic-1",
            "structural-1",
            "pue-002",
            "ontology-1",
            "discovery-1",
            "governance-1",
        ),
        None,
        now,
        None,
    )


def test_governance_history_and_effective_decision_reconstruct_after_restart(tmp_path):
    database = tmp_path / "restart.db"
    scope = DecisionScope(
        "analysis-1", "prospect-1", "org-1", "tenant-1", "source-1", "file-1", "sheet-1", "column-1"
    )
    first = DurableRuntimeComposition(database)
    first.decisions.append(_decision(scope))
    first.decisions.append(_decision(scope, "decision-2", MappingDecisionState.OVERRIDDEN))
    del first

    second = DurableRuntimeComposition(database)
    history = second.decisions.history(scope)
    assert [item.decision_id for item in history.decisions] == ["decision-1", "decision-2"]
    assert second.decisions.effective(scope).decision_id == "decision-2"
    reconstructed_governance = ConfirmationService(repository=second.decisions)
    assert reconstructed_governance.repository.effective(scope).decision_id == "decision-2"


def test_durable_composition_rebuilds_confirmation_service_over_persisted_state(tmp_path):
    runtime = DurableRuntimeComposition(tmp_path / "services.db")
    scope = DecisionScope(
        "analysis-1", "prospect-1", "org-1", "tenant-1", "source", "file", "sheet", "column"
    )
    runtime.decisions.append(_decision(scope))
    rebuilt = DurableRuntimeComposition(tmp_path / "services.db")
    service = ConfirmationService(repository=rebuilt.decisions)
    assert service.repository.effective(scope).decision_id == "decision-1"


def test_cross_scope_direct_id_read_is_rejected_after_restart(tmp_path):
    runtime = DurableRuntimeComposition(tmp_path / "scope.db")
    scope = DecisionScope(
        "analysis-1", "prospect-a", "org-1", "tenant-a", "source", "file", "sheet", "column"
    )
    runtime.decisions.append(_decision(scope))
    foreign = DecisionScope(
        "analysis-1", "prospect-b", "org-1", "tenant-a", "source", "file", "sheet", "column"
    )
    assert runtime.decisions.history(foreign).decisions == ()


def test_answer_reference_survives_restart_but_is_scoped(tmp_path):
    database = tmp_path / "answer.db"
    scope = LifecycleScope("org-1", "tenant-1", "prospect-1", "analysis-1")
    first = DurableRuntimeComposition(database)
    first.answers.save("answer-fp", scope, references=("plan-1", "result-1"))
    del first
    second = DurableRuntimeComposition(database)
    assert second.answers.load("answer-fp", scope).payload == {"references": ["plan-1", "result-1"]}
    with pytest.raises(Exception):
        second.answers.load(
            "answer-fp", LifecycleScope("org-1", "tenant-1", "prospect-2", "analysis-1")
        )


def test_reconciliation_binding_survives_restart_without_duplicate_state(tmp_path):
    database = tmp_path / "binding.db"
    scope = ("org-1", "tenant-1", "prospect-1", "analysis-1")
    binding = SourceIdentityBinding(
        "binding-1",
        "binding-fp-1",
        scope,
        "aws",
        "i-test123",
        EntityType.CLOUD_RESOURCE,
        "cloud-resource-1",
        None,
        "native_identifier",
        ("aws:row-1",),
        datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    first = DurableRuntimeComposition(database)
    first.reconciliation.save_binding(binding)
    first.reconciliation.save_binding(binding)
    del first
    second = DurableRuntimeComposition(database)
    loaded = second.reconciliation.bindings(LifecycleScope(*scope))
    assert len(loaded) == 1
    assert loaded[0].canonical_entity_id == "cloud-resource-1"
    rebuilt = second.build_reconciliation_service(
        type("Registry", (), {})(), LifecycleScope(*scope)
    )
    assert rebuilt._bindings


def test_durable_composition_requires_database_instead_of_ephemeral_fallback():
    with pytest.raises(ValueError, match="durable lifecycle database is required"):
        DurableRuntimeComposition(None)
