"""Fail-closed release evidence; these tests do NOT certify a missing baseline."""

import json
from pathlib import Path

import pytest

from scripts.audit_database_bootstrap import build_inventory, build_manifest, strip_comments

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/cmp/CMP-P6-DEF-001"


@pytest.fixture(scope="module")
def inventory():
    return build_inventory()


def test_inventory_reproducible(inventory):
    assert inventory == json.loads((EVIDENCE / "schema_inventory.json").read_text())


def test_manifest_covers_exact_current_chains_and_hashes():
    manifest = json.loads((EVIDENCE / "migration_manifest.json").read_text())
    assert manifest == build_manifest()
    steps = manifest["steps"]
    assert len(steps[1]["files"]) == 17
    assert len(steps[2]["files"]) == 23
    assert [Path(f["path"]).name[:4] for f in steps[2]["files"]] == [
        f"{n:04d}" for n in range(1, 24)
    ]
    assert steps[3]["engine"] == "sqlite"


def test_current_manifest_is_ready_for_replay_not_execution_certification():
    manifest = build_manifest()
    assert manifest["status"] == "READY_FOR_REPLAY"
    assert manifest["executable"] is True
    assert manifest["contract"]["postgres_replay"] == "NOT_EXECUTED"
    assert not manifest["blockers"]
    assert len(manifest["steps"][5]["files"]) == 2
    assert manifest["steps"][5]["requires"] == ["source_fact_local_authority"]
    assert manifest["steps"][0]["status"] == "SCHEMA_ONLY_CURRENT_CHAIN_PREREQUISITES"


def test_prerequisites_schema_only_and_fail_closed():
    import re

    sql = strip_comments((ROOT / build_manifest()["steps"][0]["path"]).read_text()).lower()
    assert set(re.findall(r"create table public\.(\w+)", sql)) == {
        "clients",
        "organizations",
        "recommendations",
        "report_history",
        "users",
        "nexora_v1_approval_requests",
        "nexora_v1_approval_history",
    }
    assert not re.search(r"\b(insert into|copy\s|update public\.|delete from)\b", sql)
    assert not re.search(r"'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}'", sql)
    assert sql.count("enable row level security") == 7
    assert "requires an empty public application schema" in sql


def test_first_migration_prerequisites_are_explicit(inventory):
    assert inventory["dated_dependency_graph"][0]["pre_chain_or_unresolved"] == [
        "public.clients",
        "public.organizations",
        "public.recommendations",
        "public.report_history",
        "public.users",
    ]
    for name in ("clients", "organizations", "recommendations", "users"):
        assert "backups/schema_v1.sql" in inventory["definition_sources"]["public." + name]


def test_renamed_rpc_dependencies_have_providers(inventory):
    for name in ("tenant_cloud_financial_posture_v1", "tenant_cloud_financial_posture_fg001_base"):
        assert inventory["definition_sources"]["public." + name]
        assert not any(
            "public." + name in edge["pre_chain_or_unresolved"]
            for edge in inventory["dated_dependency_graph"]
        )


def test_missing_application_objects_not_silently_ignored(inventory):
    missing = {c["name"] for c in inventory["missing_literal_call_definitions"]}
    assert {"approval_requests", "approval_history"} <= missing
    assert (
        not {"application_registry", "application_spend_mapping", "technology_inventory"} & missing
    )
    assert inventory["dynamic_calls"]
    assert inventory["status"] == "READY_FOR_REPLAY"


def test_unsafe_historical_files_not_deployment_inputs(inventory):
    records = {r["path"]: r for r in inventory["sql_files"]}
    for path in ("backups/schema_v1.sql", "supabase/connector_tenancy.sql"):
        assert records[path]["classification"] == "UNSAFE_TO_REPLAY"
    paths = {f["path"] for step in build_manifest()["steps"] for f in step.get("files", [])}
    assert not any(path.startswith(("backups/", "backup_unused/", "archive/")) for path in paths)


def test_comment_scanner_preserves_literals_and_lines():
    source = "-- fake public.missing\nselect '--real', 'it''s /* real */'; /* comment */\n"
    stripped = strip_comments(source)
    assert len(stripped) == len(source)
    assert stripped.count("\n") == source.count("\n")
    assert "public.missing" not in stripped
    assert "'--real'" in stripped
    assert "'it''s /* real */'" in stripped


@pytest.mark.parametrize(
    "missing",
    [
        "migrations/connectors/0002_add_m365_provider.sql",
        "migrations/data_fabric/0022_create_source_fact_authority.sql",
        "supabase/migrations/202607260001_aws_cur_ingestion_foundation.sql",
    ],
)
def test_missing_required_migration_keeps_contract_blocked(monkeypatch, missing):
    from scripts import audit_database_bootstrap as audit

    original = audit.tracked
    monkeypatch.setattr(
        audit, "tracked", lambda suffix: [path for path in original(suffix) if path != missing]
    )
    result = audit.bootstrap_contract()
    assert result["status"] == "BLOCKED"
    assert result["blockers"]


def test_missing_prerequisite_definition_blocks_deployment(monkeypatch):
    from scripts import audit_database_bootstrap as audit

    original = audit.sql_inventory

    def missing_definition(paths):
        rows, definitions = original(paths)
        for row in rows:
            if row["path"] == audit.PREREQUISITES:
                row["objects"] = [
                    item for item in row["objects"] if item["name"] != "public.organizations"
                ]
        return rows, definitions

    monkeypatch.setattr(audit, "sql_inventory", missing_definition)
    assert audit.bootstrap_contract()["status"] == "BLOCKED"
