"""Explicit DB-API boundary for supplied idle connections; never creates one.

This source adapter is not enabled or added to the release allowlist. Existing SQL
owner RPCs are closed. Unexpected success from those unqualified RPCs is rejected.
There is no PostgREST multi-request emulation of a transaction.
"""
import json

from auth.authenticated_tenant import ProtectedWorkflowUnavailable
from services.g08_transaction_boundary import execute_once


class G08DbapiTransaction:
    def __init__(self, connection):
        # Psycopg2's established transaction-status API: 0 is IDLE. Unknown
        # drivers/active transactions/autocommit require a separately reviewed adapter.
        if (getattr(connection, "autocommit", True) is not False
                or not callable(getattr(connection, "get_transaction_status", None))
                or not callable(getattr(connection, "set_session", None))
                or connection.get_transaction_status() != 0):
            raise ProtectedWorkflowUnavailable("An idle explicit-transaction connection is required")
        self.connection = connection
        self.cursor = None
        self.locked = False

    def begin_read_committed(self):
        self.connection.set_session(isolation_level="READ COMMITTED", autocommit=False)
        self.cursor = self.connection.cursor()
        try:
            self.cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        except BaseException:
            self.connection.rollback()
            self.cursor.close()
            raise

    def acquire_global_lock(self):
        self.cursor.execute("SELECT public.g08_lock_identity_history()")
        self.locked = True

    def check_history(self):
        if not self.locked:
            raise ProtectedWorkflowUnavailable("Protected history requires the global lock")
        self.cursor.execute("SELECT public.g08_assert_identity_history()")
        self.cursor.execute("SELECT public.g08_assert_owner_history()")

    def invoke_closed_owner_boundary(self, action, context):
        if not self.locked:
            raise ProtectedWorkflowUnavailable("Protected operation requires the global lock")
        commands = {
            "ADMISSION": "SELECT public.g08_control_owner_operation(%s,%s::jsonb)",
            "REVOCATION": "SELECT public.g08_control_owner_operation(%s,%s::jsonb)",
            "INVALIDATION": "SELECT public.g08_control_owner_operation(%s,%s::jsonb)",
            "EXECUTION": "SELECT public.g08_control_owner_operation(%s,%s::jsonb)",
            "RECONCILIATION": "SELECT public.g08_read_owner_operation_receipt(%s::jsonb)",
            "STATUS_RECONCILIATION": "SELECT public.g08_read_owner_authorization_status(%s::jsonb)",
        }
        if action not in commands:
            raise ValueError("Unsupported owner action")
        data = json.dumps(context, allow_nan=False)
        parameters = (action, data) if action in {"ADMISSION", "REVOCATION", "INVALIDATION", "EXECUTION"} else (data,)
        self.cursor.execute(commands[action], parameters)
        # The approved SQL still deliberately raises. Do not turn a changed RPC,
        # arbitrary JSON or a precommit row into a fabricated durable outcome.
        raise ProtectedWorkflowUnavailable("Unqualified owner RPC unexpectedly returned; reconciliation required")

    def commit(self):
        try:
            self.connection.commit()
        finally:
            self.cursor.close()

    def rollback(self):
        try:
            self.connection.rollback()
        finally:
            if self.cursor is not None:
                self.cursor.close()


def invoke_owner_on_supplied_connection(connection, action, context):
    tx = G08DbapiTransaction(connection)

    def operation():
        tx.acquire_global_lock()
        tx.check_history()
        return tx.invoke_closed_owner_boundary(action, context)

    return execute_once(tx, operation)
