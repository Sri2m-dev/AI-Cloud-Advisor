"""Offline artifact assertions and mocked commit protocol, NOT PostgreSQL tests."""

from pathlib import Path
import re

import pytest

from services.g08_transaction_boundary import (
    CommitOutcomeUnknown,
    DurableReceipt,
    execute_once,
    reconcile_exact,
)

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "database/contracts/g08_m2a"
FOUNDATION = (SQL / "S020_integrity.sql").read_text()
ENFORCEMENT = (SQL / "A020A_enforcement.sql").read_text()
WRITER = (SQL / "A020A_private_writer.sql").read_text()
TABLES = re.findall(r"CREATE TABLE public\.(g08_\w+)", FOUNDATION)


def test_explicit_table_security_and_trigger_inventory():
    assert len(TABLES) == len(set(TABLES)) == 11
    for table in TABLES:
        assert f"'{table}'" in FOUNDATION
        assert f"'{table}'" in ENFORCEMENT
    for expected in ["ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY",
                     "REVOKE ALL ON TABLE", "FOR SELECT TO nxr_g08_history_check_owner USING (true)"]:
        assert expected in FOUNDATION
    for expected in ["BEFORE TRUNCATE", "BEFORE INSERT OR UPDATE OR DELETE",
                     "CREATE CONSTRAINT TRIGGER", "DEFERRABLE INITIALLY DEFERRED"]:
        assert expected in ENFORCEMENT


def test_composite_cycles_and_single_consumption_are_explicit():
    assert FOUNDATION.count("DEFERRABLE INITIALLY DEFERRED") == 4
    for key in ["g08_current_version_fk", "g08_origin_event_fk", "g08_version_event_fk", "g08_event_version_fk"]:
        assert key in FOUNDATION
    assert "request_id uuid UNIQUE" in FOUNDATION
    assert "owner_operation_id uuid UNIQUE" in FOUNDATION
    assert "UNIQUE(scope_key,operation,idempotency_key)" in FOUNDATION
    assert "ON DELETE CASCADE" not in FOUNDATION


def test_checker_is_read_only_and_visibility_fails_closed():
    checker = ENFORCEMENT.split("CREATE FUNCTION public.g08_assert_identity_history()", 1)[1].split("END $$;", 1)[0]
    assert "SECURITY DEFINER" in checker
    assert "SET search_path=pg_catalog SET row_security=on" in checker
    assert "pg_get_expr(pol.polqual,pol.polrelid)='true'" in checker
    assert "NOT pol.polpermissive" in checker
    executable = re.sub(r"--[^\n]*", "", checker)
    assert not re.search(r"\b(INSERT|UPDATE|DELETE|TRUNCATE|EXECUTE|pg_advisory_xact_lock)\b", executable, re.I)
    assert "EXCEPTION WHEN" not in checker
    assert "NOBYPASSRLS" in FOUNDATION


@pytest.mark.parametrize("invariant", [
    "v.revision<>n", "e.before_revision IS DISTINCT FROM n-1", "p.revoked_at IS NOT NULL",
    "h.canonical_request IS DISTINCT FROM expected", "h.result IS DISTINCT FROM r",
    "w.occurred_at<=e.occurred_at", "o.approval_refs IS DISTINCT FROM ids",
    "n=0 OR n<>c.revision", "G08 orphan history or receipt",
])
def test_history_invariants_are_present(invariant):
    assert invariant in ENFORCEMENT


def test_private_writer_cannot_become_runtime_authority():
    assert "SECURITY INVOKER" in WRITER
    assert "FROM PUBLIC,anon,authenticated,service_role,nxr_g08_identity_fn_owner" in WRITER
    assert "GRANT INSERT" not in FOUNDATION + ENFORCEMENT + WRITER
    assert "POLICY_UNRESOLVED" in ENFORCEMENT
    assert "GRANT EXECUTE ON FUNCTION public.g08_stage" not in WRITER


def test_lock_reads_clock_and_writes_are_ordered():
    assert "transaction_isolation') <> 'read committed'" in ENFORCEMENT
    assert "pg_advisory_xact_lock(16002003001::bigint)" in ENFORCEMENT
    assert WRITER.index("PERFORM public.g08_lock_identity_history()") < WRITER.index("SELECT * INTO c")
    assert WRITER.index("SELECT * INTO c") < WRITER.index("decision_time:=pg_catalog.clock_timestamp()")
    assert WRITER.index("decision_time:=pg_catalog.clock_timestamp()") < WRITER.index("INSERT INTO")
    assert "SET timezone='UTC'" in WRITER


class FakeTransaction:
    def __init__(self, commit_error=None):
        self.calls = []
        self.commit_error = commit_error

    def begin_read_committed(self):
        self.calls.append("begin_read_committed")

    def commit(self):
        self.calls.append("commit")
        if self.commit_error:
            raise self.commit_error

    def rollback(self):
        self.calls.append("rollback")


def test_completion_only_after_commit_ack():
    tx = FakeTransaction()

    def operation():
        assert tx.calls == ["begin_read_committed"]
        tx.calls.append("staged")
        return {"event_id": "e"}

    assert execute_once(tx, operation) == DurableReceipt({"event_id": "e"})
    assert tx.calls == ["begin_read_committed", "staged", "commit"]


def test_precommit_failure_rolls_back_without_completion():
    tx = FakeTransaction()

    def rejected():
        raise ValueError("incomplete evidence")

    with pytest.raises(ValueError):
        execute_once(tx, rejected)
    assert tx.calls == ["begin_read_committed", "rollback"]


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionError(), RuntimeError("deferred constraint failure")])
def test_unacknowledged_commit_stops_without_retry(error):
    tx = FakeTransaction(commit_error=error)
    attempts = []
    with pytest.raises(CommitOutcomeUnknown):
        execute_once(tx, lambda: attempts.append("once"))
    assert attempts == ["once"]
    assert tx.calls == ["begin_read_committed", "commit"]


def receipt():
    return {"event_id": "e", "canonical_request": {"key": "same"},
            "actor_auth_uid": "actor", "result": {"event_id": "e"}}


def reconcile(value):
    return reconcile_exact(expected_canonical={"key": "same"}, expected_actor="actor", authorized_read=lambda: value)


def test_authorized_exact_reconciliation_returns_original():
    assert reconcile(receipt()) == DurableReceipt({"event_id": "e"})


@pytest.mark.parametrize("value", [None, {}, {"result": {}},
    {**receipt(), "actor_auth_uid": "other"},
    {**receipt(), "canonical_request": {"key": "new"}},
    {**receipt(), "result": {"event_id": "orphan"}},
    {**receipt(), "result": None},
])
def test_missing_conflicting_or_incomplete_reconciliation_stays_unknown(value):
    with pytest.raises(CommitOutcomeUnknown):
        reconcile(value)


def test_reconciliation_does_not_swallow_current_authorization_denial():
    def denied():
        raise PermissionError("no current receipt entitlement")

    with pytest.raises(PermissionError):
        reconcile_exact(expected_canonical={}, expected_actor="a", authorized_read=denied)
