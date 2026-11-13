"""Driver-independent G08 commit boundary. No connections or retry side effects.

The injected operation must use the approved DB interface in one READ COMMITTED
transaction. A staged SQL return is never exposed as a durable receipt. This is
not an identity verifier, receipt reader entitlement, or automatic retry engine.
"""

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class Transaction(Protocol):
    def begin_read_committed(self) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


class CommitOutcomeUnknown(RuntimeError):
    """Stop mutations; reconcile the same operation/key via authorized reads."""


@dataclass(frozen=True)
class DurableReceipt:
    value: Any


def execute_once(transaction: Transaction, operation: Callable[[], Any]) -> DurableReceipt:
    transaction.begin_read_committed()
    try:
        staged = operation()
    except BaseException:
        transaction.rollback()
        raise
    try:
        transaction.commit()
    except BaseException as error:
        # Even a timeout can follow a successful server commit. No fresh key,
        # blind retry, or rollback claim can resolve a lost acknowledgement.
        raise CommitOutcomeUnknown("commit unacknowledged; authorized reconciliation required") from error
    return DurableReceipt(staged)


def reconcile_exact(
    *,
    expected_canonical: dict,
    expected_actor: str,
    authorized_read: Callable[[], dict | None],
) -> DurableReceipt:
    """Read committed receipt only through a currently authorized D10 adapter.

    Absence does not establish permission to retry. Interface binding and
    PostgreSQL receipt consistency belong to the reviewed adapter/checker.
    """
    receipt = authorized_read()
    if receipt is None:
        raise CommitOutcomeUnknown("receipt absent; keep operation quarantined")
    required = {"canonical_request", "actor_auth_uid", "result", "event_id"}
    if not required.issubset(receipt) or not isinstance(receipt["result"], dict):
        raise CommitOutcomeUnknown("incomplete receipt; fail closed")
    if receipt["canonical_request"] != expected_canonical or receipt["actor_auth_uid"] != expected_actor:
        raise CommitOutcomeUnknown("receipt conflict; fail closed")
    if not receipt["event_id"] or receipt["result"].get("event_id") != receipt["event_id"]:
        raise CommitOutcomeUnknown("receipt event mismatch; fail closed")
    return DurableReceipt(receipt["result"])
