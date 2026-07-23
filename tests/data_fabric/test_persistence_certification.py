"""P3 persistence certification guardrails."""

from __future__ import annotations

from pathlib import Path

from data_fabric.adapters.supabase import (
    SupabaseAtomicWriteExecutor,
    SupabaseEntityRepository,
    SupabaseIdempotencyRepository,
    SupabaseLineageRepository,
    SupabaseOntologyRepository,
    SupabaseProvenanceRepository,
    SupabaseQualityAssessmentRepository,
    SupabaseRelationshipRepository,
    SupabaseSemanticMappingRepository,
    SupabaseVersionRepository,
)
from data_fabric.persistence.interfaces import (
    EntityRepository,
    IdempotencyRepository,
    LineageRepository,
    OntologyRepository,
    ProvenanceRepository,
    QualityAssessmentRepository,
    RelationshipRepository,
    SemanticMappingRepository,
    VersionRepository,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations" / "data_fabric"
SUPABASE = ROOT / "data_fabric" / "adapters" / "supabase"

EXPECTED_MIGRATIONS = [
    "0001_create_data_fabric_schema.sql",
    "0002_create_enterprise_entities.sql",
    "0003_create_entity_update_rpc.sql",
    "0004_create_enterprise_relationships.sql",
    "0005_create_entity_versions.sql",
    "0006_create_lineage_events.sql",
    "0007_create_provenance_records.sql",
    "0008_create_relationship_update_rpc.sql",
    "0009_create_quality_assessments.sql",
    "0010_create_ontology_concepts.sql",
    "0011_create_ontology_relationships.sql",
    "0012_create_semantic_mappings.sql",
    "0013_create_idempotency_records.sql",
    "0014_create_ontology_update_rpcs.sql",
    "0015_create_semantic_mapping_update_rpc.sql",
    "0016_create_idempotency_state_rpcs.sql",
    "0017_create_atomic_entity_write_rpc.sql",
    "0018_create_atomic_relationship_write_rpc.sql",
    "0019_create_stewardship_persistence.sql",
    "0020_create_stewardship_rpcs.sql",
]

TABLE_MIGRATIONS = {
    "enterprise_entities": "0002_create_enterprise_entities.sql",
    "enterprise_relationships": "0004_create_enterprise_relationships.sql",
    "entity_versions": "0005_create_entity_versions.sql",
    "lineage_events": "0006_create_lineage_events.sql",
    "provenance_records": "0007_create_provenance_records.sql",
    "quality_assessments": "0009_create_quality_assessments.sql",
    "ontology_concepts": "0010_create_ontology_concepts.sql",
    "ontology_relationships": "0011_create_ontology_relationships.sql",
    "semantic_mappings": "0012_create_semantic_mappings.sql",
    "idempotency_records": "0013_create_idempotency_records.sql",
}

PRIVILEGED_RPC_FILES = [
    "0003_create_entity_update_rpc.sql",
    "0008_create_relationship_update_rpc.sql",
    "0014_create_ontology_update_rpcs.sql",
    "0015_create_semantic_mapping_update_rpc.sql",
    "0016_create_idempotency_state_rpcs.sql",
    "0017_create_atomic_entity_write_rpc.sql",
    "0018_create_atomic_relationship_write_rpc.sql",
    "0020_create_stewardship_rpcs.sql",
]


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text().lower()


def test_expected_adapter_classes_import_and_match_contracts():
    assert issubclass(SupabaseEntityRepository, EntityRepository)
    assert issubclass(SupabaseRelationshipRepository, RelationshipRepository)
    assert issubclass(SupabaseVersionRepository, VersionRepository)
    assert issubclass(SupabaseLineageRepository, LineageRepository)
    assert issubclass(SupabaseProvenanceRepository, ProvenanceRepository)
    assert issubclass(SupabaseQualityAssessmentRepository, QualityAssessmentRepository)
    assert issubclass(SupabaseOntologyRepository, OntologyRepository)
    assert issubclass(SupabaseSemanticMappingRepository, SemanticMappingRepository)
    assert issubclass(SupabaseIdempotencyRepository, IdempotencyRepository)
    assert hasattr(SupabaseAtomicWriteExecutor, "execute_entity_write")
    assert hasattr(SupabaseAtomicWriteExecutor, "execute_relationship_write")


def test_migration_sequence_complete_0001_through_0020():
    assert sorted(path.name for path in MIGRATIONS.glob("*.sql")) == EXPECTED_MIGRATIONS


def test_every_required_table_migration_enables_rls_and_no_anonymous_policy():
    combined = "\n".join(_sql(path.name) for path in MIGRATIONS.glob("*.sql"))
    assert "create policy" not in combined
    assert " to anon" not in combined
    assert " to anonymous" not in combined
    for table, filename in TABLE_MIGRATIONS.items():
        sql = _sql(filename)
        assert f"alter table data_fabric.{table} enable row level security" in sql


def test_append_only_mutation_triggers_exist():
    for table in ("entity_versions", "lineage_events", "provenance_records", "quality_assessments"):
        combined = "\n".join(_sql(path.name) for path in MIGRATIONS.glob("*.sql"))
        assert f"prevent_{table}_mutation" in combined
        assert f"before update on data_fabric.{table}" in combined
        assert f"before delete on data_fabric.{table}" in combined


def test_privileged_rpcs_have_safe_search_path_and_restricted_execute():
    for filename in PRIVILEGED_RPC_FILES:
        sql = _sql(filename)
        assert "security definer" in sql
        assert "set search_path = data_fabric, pg_temp" in sql
        assert "revoke all on function data_fabric." in sql
        assert " from public" in sql
        assert "grant execute on function data_fabric." in sql
        assert " to service_role" in sql


def test_expected_optimistic_concurrency_and_atomic_rpcs_exist():
    combined = "\n".join(_sql(path.name) for path in MIGRATIONS.glob("*.sql"))
    for function_name in (
        "data_fabric_update_enterprise_entity",
        "data_fabric_update_enterprise_relationship",
        "data_fabric_update_ontology_concept",
        "data_fabric_update_ontology_relationship",
        "data_fabric_update_semantic_mapping",
        "data_fabric_atomic_entity_write",
        "data_fabric_atomic_relationship_write",
    ):
        assert f"create or replace function data_fabric.{function_name}" in combined
    assert "p_expected_revision" in combined
    assert "revision = revision + 1" in combined or "revision=revision+1" in combined


def test_repositories_and_rpcs_remain_tenant_scoped():
    adapter_text = "\n".join(path.read_text().lower() for path in SUPABASE.glob("*.py"))
    migration_text = "\n".join(_sql(path.name) for path in MIGRATIONS.glob("*.sql"))
    assert "tenantcontext" in adapter_text
    assert ".eq(\"organization_id\"" in adapter_text
    assert ".eq(\"tenant_id\"" in adapter_text
    assert "organization_id = " in migration_text or "organization_id=" in migration_text
    assert "tenant_id = " in migration_text or "tenant_id=" in migration_text


def test_no_automatic_migration_execution_or_runtime_supabase_adapter_imports():
    adapter_text = "\n".join(path.read_text(errors="ignore").lower() for path in SUPABASE.glob("*.py"))
    forbidden_runtime_roots = ("pages", "services", "connectors", "connector_runtime", "components")
    runtime_text = ""
    for root_name in forbidden_runtime_roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        runtime_text += "\n".join(path.read_text(errors="ignore").lower() for path in root.rglob("*.py"))
    assert "data_fabric.adapters.supabase" not in runtime_text
    combined_boundary_text = adapter_text + "\n" + runtime_text
    assert "run migrations" not in combined_boundary_text
    assert "execute migrations" not in combined_boundary_text
    assert "startup migration" not in combined_boundary_text


def test_sql_safety_scan_has_no_destructive_statements_or_production_urls():
    combined = "\n".join(_sql(path.name) for path in MIGRATIONS.glob("*.sql"))
    for forbidden in ("drop table", "drop schema", "truncate", "delete from", "postgres://", "postgresql://", "supabase.co"):
        assert forbidden not in combined
