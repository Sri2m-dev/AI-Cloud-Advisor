from __future__ import annotations

import sqlite3

import pytest

from universal_evidence.persistence import (
    LifecyclePersistenceError,
    LifecycleScope,
    SQLiteLifecycleRepository,
)


def test_lifecycle_state_survives_repository_restart_and_is_idempotent(tmp_path):
    database = tmp_path / "lifecycle.db"
    scope = LifecycleScope("org-a", "tenant-a", "prospect-a", "analysis-a")
    first = SQLiteLifecycleRepository(database)
    created = first.put(
        "mapping_decision",
        "decision-1",
        scope,
        payload={"state": "CONFIRMED"},
        fingerprint_value="fp-1",
    )
    replay = first.put(
        "mapping_decision",
        "decision-1",
        scope,
        payload={"state": "CONFIRMED"},
        fingerprint_value="fp-1",
    )
    assert replay.version == created.version
    del first

    second = SQLiteLifecycleRepository(database)
    loaded = second.get("mapping_decision", "decision-1", scope)
    assert loaded.payload == {"state": "CONFIRMED"}
    assert loaded.fingerprint == "fp-1"
    assert len(second.audit_events(scope)) == 2


def test_scope_is_required_for_direct_id_reads(tmp_path):
    repository = SQLiteLifecycleRepository(tmp_path / "scope.db")
    scope = LifecycleScope("org-a", "tenant-a", "prospect-a", "analysis-a")
    repository.put("answer", "answer-1", scope, payload={"answer_fingerprint": "fp"})
    with pytest.raises(LifecyclePersistenceError):
        repository.get(
            "answer", "answer-1", LifecycleScope("org-a", "tenant-a", "prospect-b", "analysis-a")
        )
    with pytest.raises(LifecyclePersistenceError):
        repository.get(
            "answer", "answer-1", LifecycleScope("org-b", "tenant-a", "prospect-a", "analysis-a")
        )


def test_lifecycle_versions_and_stale_states_are_preserved(tmp_path):
    repository = SQLiteLifecycleRepository(tmp_path / "states.db")
    scope = LifecycleScope("org-a", "tenant-a", "prospect-a", "analysis-a")
    repository.put("authorization", "auth-1", scope, fingerprint_value="auth-v1")
    expired = repository.mark_state(
        "authorization", "auth-1", scope, "EXPIRED", reason="authorization superseded"
    )
    assert expired.state == "EXPIRED"
    assert expired.fingerprint == "auth-v1"
    assert expired.version == 2


def test_scoped_purge_removes_payloads_and_retains_minimal_tombstones(tmp_path):
    repository = SQLiteLifecycleRepository(tmp_path / "purge.db")
    scope_a = LifecycleScope("org-a", "tenant-a", "prospect-a", "analysis-a")
    scope_b = LifecycleScope("org-a", "tenant-a", "prospect-b", "analysis-b")
    repository.put("normalization", "run-a", scope_a, payload={"fingerprint": "run-a"})
    repository.put("normalization", "run-b", scope_b, payload={"fingerprint": "run-b"})
    assert repository.purge_scope(scope_a, actor_id="admin", reason="retention expiry") == 1
    assert repository.list_scope(scope_a) == ()
    tombstones = repository.list_scope(scope_a, include_purged=True)
    assert (
        len(tombstones) == 1 and tombstones[0].state == "PURGED" and tombstones[0].payload is None
    )
    assert repository.get("normalization", "run-b", scope_b).payload == {"fingerprint": "run-b"}
    assert any(
        item["event_type"] == "LIFECYCLE_PURGED" for item in repository.audit_events(scope_a)
    )


def test_payload_bytes_are_rejected_and_database_integrity_holds(tmp_path):
    database = tmp_path / "integrity.db"
    repository = SQLiteLifecycleRepository(database)
    with pytest.raises(ValueError, match="raw evidence bytes"):
        repository.put(
            "evidence", "file-1", LifecycleScope("org-a", "tenant-a"), payload={"bytes": b"secret"}
        )
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()
