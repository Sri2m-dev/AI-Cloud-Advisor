from __future__ import annotations

from pathlib import Path


DOCS = {
    "docs/architecture/ADR-016-Data-Fabric-Persistence-Architecture.md": (
        "Data Fabric Persistence Architecture",
        "GO WITH CONDITIONS",
        "architecture only",
    ),
    "docs/P3_PERSISTENCE_ARCHITECTURE.md": (
        "Repository Boundaries",
        "Write Flow",
        "design only",
    ),
    "docs/P3_STORAGE_MODEL.md": (
        "Current State",
        "Immutable History",
        "JSON Versus Normalized Columns",
    ),
    "docs/P3_TRANSACTION_AND_IDEMPOTENCY_MODEL.md": (
        "Transaction Boundary",
        "Idempotency Key",
        "Rollback Strategy",
    ),
    "docs/P3_DATA_FABRIC_SCHEMA_BLUEPRINT.md": (
        "Schema Blueprint",
        "Current-State Tables",
        "Row-Level Access Policy",
    ),
    "docs/P3_PERSISTENCE_IMPLEMENTATION_PLAN.md": (
        "GO WITH CONDITIONS",
        "Phase 1: Repository Interfaces",
        "Explicitly Out Of Scope",
    ),
}


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_persistence_architecture_docs_exist_and_include_required_sections():
    for path, required_terms in DOCS.items():
        content = read(path)
        for term in required_terms:
            assert term in content, f"{term} missing from {path}"


def test_adr_016_is_registered_in_architecture_index():
    content = read("docs/ARCHITECTURE_DECISION_INDEX.md")

    assert "ADR-016" in content
    assert "ADR-016-Data-Fabric-Persistence-Architecture.md" in content
    assert "ADR-008 through ADR-" in content


def test_persistence_design_declares_required_architecture_topics():
    combined = "\n".join(read(path) for path in DOCS)
    required_topics = (
        "aggregate",
        "current-state",
        "immutable",
        "tenant",
        "uniqueness",
        "indexes",
        "JSON",
        "optimistic concurrency",
        "soft delete",
        "idempotency",
        "lineage",
        "provenance",
        "semantic",
        "version",
        "rollback",
        "migration",
        "repository",
        "adapter",
    )

    for topic in required_topics:
        assert topic.lower() in combined.lower(), f"{topic} missing from persistence design"


def test_persistence_architecture_phase_does_not_wire_product_runtime_paths():
    forbidden_runtime_paths = (
        "pages/data_fabric_persistence.py",
        "connector_runtime/data_fabric_persistence.py",
        "services/data_fabric_persistence.py",
        "data_fabric/migrations",
    )

    for forbidden in forbidden_runtime_paths:
        assert not Path(forbidden).exists(), f"P3 persistence architecture should not wire runtime path: {forbidden}"


def test_persistence_docs_explicitly_defer_runtime_integration():
    combined = "\n".join(read(path) for path in DOCS)
    forbidden_runtime = (
        "dashboard changes",
        "connector runtime changes",
        "Knowledge Graph",
        "scheduler",
    )

    for phrase in forbidden_runtime:
        assert phrase in combined






