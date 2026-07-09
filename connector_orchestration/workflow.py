"""Connector workflow contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from connector_orchestration.dependency import ConnectorDependency
from connector_runtime import ConnectorExecutionPolicy


@dataclass(frozen=True)
class ConnectorWorkflowStep:
    connector_id: str
    policy: ConnectorExecutionPolicy = field(default_factory=ConnectorExecutionPolicy)
    depends_on: tuple[str, ...] = field(default_factory=tuple)

    def dependency(self) -> ConnectorDependency:
        return ConnectorDependency(connector_id=self.connector_id, depends_on=self.depends_on)


@dataclass(frozen=True)
class ConnectorWorkflow:
    workflow_id: str
    name: str
    steps: Sequence[ConnectorWorkflowStep]

    def ready_steps(self, completed: set[str]) -> list[ConnectorWorkflowStep]:
        return [step for step in self.steps if step.connector_id not in completed and all(parent in completed for parent in step.depends_on)]
