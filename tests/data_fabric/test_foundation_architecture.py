from dataclasses import fields
from datetime import datetime, timedelta, timezone
from enum import Enum
import importlib
import pkgutil
from pathlib import Path

import pytest

import data_fabric
from data_fabric.contracts import (
    EnterpriseEntity,
    EnterpriseRelationship,
    EntityQuality,
    EntityType,
    RelationshipType,
)
from data_fabric.identity import MatchCandidate
from data_fabric.lineage import LineageEvent, ProvenanceRecord
from data_fabric.quality import InMemoryDataQualityEvaluator, QualityIssue, QualityValidationError
from data_fabric.registry import InMemoryEntityRegistry, RegistryError
from data_fabric.semantic import ConceptRelationship, SemanticConcept, SemanticMapping, SemanticValidationError
from data_fabric.versioning import EntitySnapshot, TemporalRecord, VersionRecord, VersioningValidationError
from data_fabric.versioning.models import payload_hash


BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_all_public_data_fabric_package_imports_succeed() -> None:
    package_names = [
        "data_fabric.contracts",
        "data_fabric.registry",
        "data_fabric.identity",
        "data_fabric.lineage",
        "data_fabric.quality",
        "data_fabric.versioning",
        "data_fabric.semantic",
    ]

    for package_name in package_names:
        importlib.import_module(package_name)


def test_no_circular_imports_across_data_fabric_packages() -> None:
    for module in pkgutil.walk_packages(data_fabric.__path__, data_fabric.__name__ + "."):
        if module.name.startswith("data_fabric."):
            importlib.import_module(module.name)


def test_contracts_do_not_import_higher_level_packages() -> None:
    contracts_dir = Path("data_fabric/contracts")
    forbidden = (
        "data_fabric.registry",
        "data_fabric.identity",
        "data_fabric.lineage",
        "data_fabric.quality",
        "data_fabric.versioning",
        "data_fabric.semantic",
    )

    for path in contracts_dir.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), path


def test_organization_id_and_tenant_id_exist_where_required() -> None:
    checked = [
        EnterpriseEntity,
        EnterpriseRelationship,
        MatchCandidate,
        LineageEvent,
        ProvenanceRecord,
        VersionRecord,
        TemporalRecord,
        SemanticConcept,
        SemanticMapping,
    ]

    for model in checked:
        names = {field.name for field in fields(model)}
        assert "organization_id" in names, model
        assert "tenant_id" in names, model


def test_score_ranges_are_consistent_and_explicit() -> None:
    with pytest.raises(ValueError):
        EnterpriseEntity("e1", "app:e1", EntityType.APPLICATION, "App", "src", "id", "org", confidence_score=1.1)
    with pytest.raises(ValueError):
        EntityQuality(trust_score=-0.1)
    with pytest.raises(QualityValidationError):
        QualityIssue("rule", "accuracy", "bad", deduction=101.0)
    with pytest.raises(SemanticValidationError):
        SemanticMapping("m1", "src", "term", None, None, None, None, "concept", "org", "tenant", confidence=101.0)


def test_enum_values_serialize_deterministically() -> None:
    assert EntityType.APPLICATION.value == "application"
    assert RelationshipType.RUNS_ON.value == "runs_on"
    assert isinstance(EntityType.APPLICATION, Enum)
    assert isinstance(RelationshipType.RUNS_ON, Enum)


def test_public_result_objects_cannot_mutate_internal_in_memory_state() -> None:
    registry = InMemoryEntityRegistry()
    entity = EnterpriseEntity("e1", "app:e1", EntityType.APPLICATION, "App", "src", "id", "org", metadata={"tier": "one"})
    registry.register_entity(entity)
    fetched = registry.get_entity("e1")
    fetched.metadata["tier"] = "two"
    assert registry.get_entity("e1").metadata["tier"] == "one"

    snapshot = VersionRecord(
        "s1",
        "e1",
        "entity",
        "org",
        "tenant",
        1,
        BASE_TIME,
        BASE_TIME,
        None,
        "src",
        "id",
        {"metadata": {"tier": "one"}},
        payload_hash({"metadata": {"tier": "one"}}),
    )
    with pytest.raises(TypeError):
        snapshot.payload["metadata"]["tier"] = "two"

    concept = SemanticConcept("c1", "Compute", "Compute", "desc", "compute", None, "org", "tenant", attributes={"level": "root"})
    with pytest.raises(TypeError):
        concept.attributes["level"] = "child"


def test_datetime_validation_is_consistent_at_operational_boundaries() -> None:
    entity = EnterpriseEntity("e1", "app:e1", EntityType.APPLICATION, "App", "src", "id", "org")
    entity.created_at = BASE_TIME + timedelta(days=1)
    entity.updated_at = BASE_TIME
    assessment = InMemoryDataQualityEvaluator().evaluate_entity(entity)
    assert any(issue.rule_id == "entity_timestamp_order" for issue in assessment.issues)

    with pytest.raises(VersioningValidationError):
        TemporalRecord("r1", "e1", "entity", "org", "tenant", 1, BASE_TIME, BASE_TIME, BASE_TIME, {}, payload_hash({}))


def test_semantic_and_canonical_relationship_models_remain_distinct() -> None:
    canonical = EnterpriseRelationship("r1", RelationshipType.RUNS_ON, "e1", "e2", "org")
    semantic = ConceptRelationship("cr1", "compute", "vm", "is_a", "org", "tenant")

    assert canonical.source_entity_id == "e1"
    assert semantic.source_concept_id == "compute"
    assert canonical.relationship_type is RelationshipType.RUNS_ON
    assert semantic.relationship_type == "is_a"


def test_versioning_and_canonical_version_contracts_remain_compatible() -> None:
    from data_fabric.contracts import EntityVersion
    from data_fabric.versioning import InMemoryVersionStore

    entity = EnterpriseEntity(
        "e1",
        "app:e1",
        EntityType.APPLICATION,
        "App",
        "src",
        "id",
        "org",
        "tenant",
        entity_version=EntityVersion(version=1, effective_from=BASE_TIME),
    )
    snapshot = InMemoryVersionStore().create_entity_snapshot(entity)

    assert isinstance(snapshot, EntitySnapshot)
    assert snapshot.effective_from == BASE_TIME


def test_quality_assessment_references_canonical_entity_identifiers() -> None:
    entity = EnterpriseEntity("e1", "app:e1", EntityType.APPLICATION, "App", "src", "id", "org", "tenant")

    assessment = InMemoryDataQualityEvaluator().evaluate_entity(entity)

    assert assessment.subject_id == "e1"
    assert assessment.organization_id == "org"
    assert assessment.tenant_id == "tenant"


def test_package_exception_types_remain_catchable_and_predictable() -> None:
    assert issubclass(RegistryError, Exception)
    assert issubclass(SemanticValidationError, ValueError)
    assert issubclass(VersioningValidationError, ValueError)

    with pytest.raises(SemanticValidationError):
        SemanticConcept("bad", "Bad", "Bad", "desc", "not_a_type", None, "org", "tenant")
