"""Canonical persistence transaction contracts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TransactionManager:
    """Lightweight transaction state manager for persistence adapters."""

    active: bool = False
    committed: bool = False
    rolled_back: bool = False
    events: list[str] = field(default_factory=list)

    def begin(self) -> None:
        self.active = True
        self.committed = False
        self.rolled_back = False
        self.events.append("begin")

    def commit(self) -> None:
        if not self.active:
            raise RuntimeError("Cannot commit inactive transaction.")
        self.committed = True
        self.active = False
        self.events.append("commit")

    def rollback(self) -> None:
        if not self.active:
            raise RuntimeError("Cannot rollback inactive transaction.")
        self.rolled_back = True
        self.active = False
        self.events.append("rollback")

    def retry(self) -> None:
        self.events.append("retry")
