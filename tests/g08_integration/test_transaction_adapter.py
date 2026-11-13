"""Driver-adapter protocol tests with a fake connection, not PostgreSQL tests."""
import pytest

from auth.authenticated_tenant import ProtectedWorkflowUnavailable
from repositories.g08_transaction import G08DbapiTransaction, invoke_owner_on_supplied_connection
from services.g08_transaction_boundary import CommitOutcomeUnknown, execute_once


class Connection:
    autocommit = False
    def __init__(self, commit_error=None, execute_error=None):
        self.calls = []
        self.commit_error = commit_error
        self.execute_error = execute_error
    def get_transaction_status(self): return 0
    def set_session(self, **kwargs): self.calls.append(("session", kwargs))
    def cursor(self): return self
    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        if self.execute_error and "g08_control_owner_operation" in sql:
            raise self.execute_error
    def close(self): self.calls.append(("close", None))
    def commit(self):
        self.calls.append(("commit", None))
        if self.commit_error: raise self.commit_error
    def rollback(self): self.calls.append(("rollback", None))


def test_closed_sql_rpc_is_bound_and_unexpected_return_rolls_back():
    conn = Connection()
    with pytest.raises(ProtectedWorkflowUnavailable):
        invoke_owner_on_supplied_connection(conn, "EXECUTION", {"operation_id": "a');x"})
    sql = [call[0] for call in conn.calls]
    assert sql[:3] == ["session", "SET TRANSACTION ISOLATION LEVEL READ COMMITTED", "SELECT public.g08_lock_identity_history()"]
    assert sql[3:5] == ["SELECT public.g08_assert_identity_history()", "SELECT public.g08_assert_owner_history()"]
    assert "a');x" not in sql[5]
    assert sql[-2:] == ["rollback", "close"] and "commit" not in sql


def test_sql_denial_is_not_retried_or_committed():
    conn = Connection(execute_error=PermissionError("denied"))
    with pytest.raises(PermissionError):
        invoke_owner_on_supplied_connection(conn, "EXECUTION", {})
    assert sum("g08_control_owner_operation" in call[0] for call in conn.calls) == 1
    assert ("rollback", None) in conn.calls


def test_commit_loss_is_unknown_after_staged_result_without_rollback_claim():
    conn = Connection(commit_error=TimeoutError())
    tx = G08DbapiTransaction(conn)
    with pytest.raises(CommitOutcomeUnknown):
        execute_once(tx, lambda: "staged")
    assert ("rollback", None) not in conn.calls


@pytest.mark.parametrize("autocommit,status", [(True,0),(False,2),(False,1)])
def test_active_or_autocommit_connection_is_rejected(autocommit,status):
    conn = Connection()
    conn.autocommit = autocommit
    conn.get_transaction_status = lambda: status
    with pytest.raises(ProtectedWorkflowUnavailable): G08DbapiTransaction(conn)


def test_history_without_global_lock_is_denied():
    tx = G08DbapiTransaction(Connection())
    tx.begin_read_committed()
    with pytest.raises(ProtectedWorkflowUnavailable): tx.check_history()
    tx.rollback()
