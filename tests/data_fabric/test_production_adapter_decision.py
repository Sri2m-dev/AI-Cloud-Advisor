from __future__ import annotations

from pathlib import Path


DOCS = {
    "docs/architecture/ADR-017-Production-Data-Fabric-Persistence-Adapter.md": (
        "Supabase PostgreSQL",
        "GO WITH CONDITIONS",
        "architecture only",
    ),
    "docs/P3_PRODUCTION_ADAPTER_DECISION.md": (
        "Selected first production adapter target: **Supabase PostgreSQL**",
        "Why Alternatives Are Deferred",
        "Explicit Non-Implementation Statement",
    ),
    "docs/P3_DATABASE_ADAPTER_IMPLEMENTATION_PLAN.md": (
        "Package Boundary",
        "Client And Driver Strategy",
        "Exit Criteria For First Adapter Merge",
    ),
    "docs/P3_DATABASE_MIGRATION_STRATEGY.md": (
        "Migration Tooling",
        "Schema Namespace Strategy",
        "Tenant Policy",
    ),
    "docs/P3_DATABASE_TEST_STRATEGY.md": (
        "Compliance Suite Requirements",
        "Local Test Strategy",
        "CI Test Strategy",
    ),
    "docs/P3_DATABASE_OPERATIONAL_READINESS.md": (
        "Connection Management",
        "Observability",
        "Backup And Recovery",
    ),
}


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_adapter_decision_docs_exist_and_select_supabase_postgresql():
    for path, required_terms in DOCS.items():
        content = read(path)
        for term in required_terms:
            assert term in content, f"{term} missing from {path}"


def test_adr_017_is_registered_in_architecture_index():
    content = read("docs/ARCHITECTURE_DECISION_INDEX.md")

    assert "ADR-017" in content
    assert "ADR-017-Production-Data-Fabric-Persistence-Adapter.md" in content
    assert "ADR-008 through ADR-017" in content


def test_decision_evaluates_required_adapter_options_and_criteria():
    content = read("docs/P3_PRODUCTION_ADAPTER_DECISION.md")
    options = ("PostgreSQL Direct", "Supabase PostgreSQL", "SQLite Reference", "Other Relational Store")
    criteria = (
        "Production scalability",
        "Tenant isolation",
        "Transactions",
        "Optimistic concurrency",
        "JSON support",
        "Append-only history",
        "Temporal queries",
        "Indexing",
        "Local development",
        "Test automation",
        "Migration tooling",
        "Deployment complexity",
        "Observability",
        "Nexora alignment",
    )

    for option in options:
        assert option in content
    for criterion in criteria:
        assert criterion in content


def test_database_decision_phase_does_not_add_adapter_or_migration_code():
    forbidden_paths = (
        "data_fabric/persistence_adapters",
        "data_fabric/database_adapters",
        "data_fabric/adapters",
        "data_fabric/migrations",
    )

    for path in forbidden_paths:
        assert not Path(path).exists(), f"P3.12 must not add implementation path: {path}"


def test_database_decision_docs_defer_runtime_and_adapter_implementation():
    combined = "\n".join(read(path) for path in DOCS)
    required_deferrals = (
        "No adapter implementation",
        "No migration",
        "No new environment variables",
        "runtime integration",
        "dashboard",
        "connector",
        "Knowledge Graph",
    )

    for phrase in required_deferrals:
        assert phrase.lower() in combined.lower()
