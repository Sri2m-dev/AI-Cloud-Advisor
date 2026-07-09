"""Connector orchestration coordinator."""

from __future__ import annotations

from dataclasses import dataclass, field

from connector_orchestration.dependency import DependencyManager
from connector_orchestration.queue import ConnectorQueueItem, ConnectorQueueManager, QueueState
from connector_orchestration.retry import RetryPolicy
from connector_orchestration.trigger import ConnectorTrigger, ConnectorTriggerType
from connector_orchestration.workflow import ConnectorWorkflow
from connector_runtime import ConnectorExecutionEngine, ConnectorExecutionPolicy, ConnectorExecutionResult
from connector_sdk import ConnectorSyncState


@dataclass(frozen=True)
class ConnectorRunOutcome:
    queue_item: ConnectorQueueItem
    result: ConnectorExecutionResult | None
    final_state: QueueState
    retry_scheduled: bool = False


class ConnectorCoordinator:
    """Single orchestration entry point for connector execution."""

    def __init__(
        self,
        execution_engine: ConnectorExecutionEngine,
        queue_manager: ConnectorQueueManager | None = None,
        dependency_manager: DependencyManager | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.execution_engine = execution_engine
        self.queue_manager = queue_manager or ConnectorQueueManager()
        self.dependency_manager = dependency_manager or DependencyManager()
        self.retry_policy = retry_policy or RetryPolicy()

    def run(
        self,
        connector_id: str,
        *,
        trigger: ConnectorTrigger | None = None,
        policy: ConnectorExecutionPolicy | None = None,
    ) -> ConnectorRunOutcome:
        """Enqueue and run a single connector immediately."""

        trigger = trigger or ConnectorTrigger(trigger_type=ConnectorTriggerType.MANUAL)
        queued = self.queue_manager.enqueue(connector_id, trigger, policy=policy)
        return self._run_queue_item(queued)

    def run_workflow(self, workflow: ConnectorWorkflow) -> list[ConnectorRunOutcome]:
        """Run all workflow steps whose dependencies are satisfied."""

        outcomes: list[ConnectorRunOutcome] = []
        completed = set(self.dependency_manager.completed)
        while True:
            ready = workflow.ready_steps(completed)
            if not ready:
                break
            for step in ready:
                outcome = self.run(
                    step.connector_id,
                    trigger=ConnectorTrigger(trigger_type=ConnectorTriggerType.DEPENDENCY_COMPLETE, source=workflow.workflow_id),
                    policy=step.policy,
                )
                outcomes.append(outcome)
                if outcome.final_state == QueueState.COMPLETED:
                    self.dependency_manager.mark_complete(step.connector_id)
                    completed.add(step.connector_id)
                else:
                    return outcomes
        return outcomes

    def _run_queue_item(self, item: ConnectorQueueItem) -> ConnectorRunOutcome:
        running = self.queue_manager.mark(item.queue_id, QueueState.RUNNING) or item
        result = self.execution_engine.execute(running.connector_id, policy=running.policy)
        if result.state == ConnectorSyncState.SUCCEEDED:
            completed = self.queue_manager.mark(running.queue_id, QueueState.COMPLETED) or running
            return ConnectorRunOutcome(queue_item=completed, result=result, final_state=QueueState.COMPLETED)

        decision = self.retry_policy.decide(running.attempt)
        if decision.should_retry:
            retrying = self.queue_manager.mark(running.queue_id, QueueState.RETRYING, attempt=running.attempt + 1) or running
            return ConnectorRunOutcome(queue_item=retrying, result=result, final_state=QueueState.RETRYING, retry_scheduled=True)

        failed = self.queue_manager.mark(running.queue_id, QueueState.FAILED) or running
        return ConnectorRunOutcome(queue_item=failed, result=result, final_state=QueueState.FAILED)
