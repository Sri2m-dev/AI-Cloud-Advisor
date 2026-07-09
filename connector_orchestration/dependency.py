"""Connector workflow dependency management."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DependencyStatus(str, Enum):
    WAITING = "waiting"
    SATISFIED = "satisfied"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ConnectorDependency:
    connector_id: str
    depends_on: tuple[str, ...] = field(default_factory=tuple)


class DependencyManager:
    """Tracks connector dependency completion for workflows."""

    def __init__(self) -> None:
        self.completed: set[str] = set()

    def mark_complete(self, connector_id: str) -> None:
        self.completed.add(connector_id)

    def status(self, dependency: ConnectorDependency) -> DependencyStatus:
        if all(parent in self.completed for parent in dependency.depends_on):
            return DependencyStatus.SATISFIED
        return DependencyStatus.WAITING

    def can_run(self, dependency: ConnectorDependency) -> bool:
        return self.status(dependency) == DependencyStatus.SATISFIED
