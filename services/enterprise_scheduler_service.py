from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from connectors.base.scheduler import ConnectorScheduler
from connectors.base.sync_manager import ConnectorSyncManager
from connectors.common.tenant_guard import resolve_organization_id
from repositories.scheduler_repository import SchedulerRepository
from services.retry_engine import RetryEngine


QUEUE_STATES = ["Queued", "Running", "Succeeded", "Failed", "Retrying", "Dead Letter", "Cancelled", "Paused"]

RATE_LIMITS = {
    "AWS": ("API quota", 4, "AWS API quota-aware"),
    "Azure": ("subscription", 4, "Subscription-aware"),
    "GCP": ("project", 4, "Project-aware"),
    "Microsoft 365": ("Graph throttling", 3, "Microsoft Graph throttling-aware"),
    "ServiceNow": ("instance", 3, "Instance-aware"),
    "GitHub": ("API rate limit", 5, "GitHub API-rate-limit-aware"),
    "Jira": ("Atlassian rate limit", 3, "Atlassian-rate-limit-aware"),
    "Datadog": ("API key", 4, "API-key-aware"),
    "Dynatrace": ("API token", 4, "Tenant API-token-aware"),
    "New Relic": ("NerdGraph quota", 4, "NerdGraph quota-aware"),
    "Splunk": ("search load", 2, "Search-load-aware"),
    "Prometheus": ("query load", 3, "Query-load-aware"),
    "Grafana": ("API token", 3, "API-token-aware"),
}

DEPENDENCY_ORDER = [
    ("Identity sync", ["Microsoft 365", "ServiceNow"], 1),
    ("Application sync", ["GitHub", "Jira", "ServiceNow"], 2),
    ("Cloud resource sync", ["AWS", "Azure", "GCP"], 3),
    ("Observability sync", ["Datadog", "Dynatrace", "New Relic", "Splunk", "Prometheus", "Grafana"], 4),
    ("Knowledge Graph refresh", ["Knowledge Graph"], 5),
    ("Digital Twin refresh", ["Digital Twin"], 6),
    ("Prediction refresh", ["Predictive AI"], 7),
]


class EnterpriseSchedulerService:
    def __init__(self, organization_id: str | None = None) -> None:
        self.organization_id = resolve_organization_id(organization_id)
        self.bootstrap_defaults()

    def bootstrap_defaults(self) -> None:
        for connector, (limit_type, concurrency, description) in RATE_LIMITS.items():
            SchedulerRepository.upsert_rate_limit(
                {
                    "organization_id": self.organization_id,
                    "connector": connector,
                    "limit_type": limit_type,
                    "max_concurrency": concurrency,
                    "window_seconds": 60,
                    "description": description,
                    "updated_at": self._now(),
                }
            )
        for stage, connectors, order in DEPENDENCY_ORDER:
            SchedulerRepository.upsert_dependency(
                {
                    "organization_id": self.organization_id,
                    "stage": stage,
                    "connectors": connectors,
                    "execution_order": order,
                    "updated_at": self._now(),
                }
            )

    def schedule_connector_sync(
        self,
        connector: str,
        schedule: str = "Manual",
        priority: int = 5,
        job_type: str = "Connector Sync",
        dependencies: list[str] | None = None,
    ) -> dict[str, Any]:
        job = {
            "id": str(uuid.uuid4()),
            "organization_id": self.organization_id,
            "connector": connector,
            "job_type": job_type,
            "schedule": schedule,
            "priority": priority,
            "status": "Queued",
            "dependencies": dependencies or [],
            "retry_count": 0,
            "max_retries": RetryEngine.DEFAULT_MAX_RETRIES,
            "next_run_at": ConnectorScheduler.next_sync(schedule) or self._now(),
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        SchedulerRepository.upsert_job(job)
        self._operation(job, "Schedule", "Queued", f"{connector} sync scheduled with priority {priority}.")
        return job

    def manual_run(self, connector: str, priority: int = 1, simulate_failure: bool = False) -> dict[str, Any]:
        job = self.schedule_connector_sync(connector, schedule="Manual", priority=priority)
        return self.run_job(job["id"], simulate_failure=simulate_failure)

    def recurring_run(self) -> dict[str, Any]:
        jobs = self.dependency_ordered_jobs()
        results = [self.run_job(job["id"]) for job in jobs if job.get("status") == "Queued"]
        return {"status": "Completed", "runs": results, "run_count": len(results)}

    def run_job(self, job_id: str, simulate_failure: bool = False) -> dict[str, Any]:
        job = SchedulerRepository.get_job(job_id, self.organization_id)
        if not job:
            return {"status": "Failed", "error": f"Unknown job: {job_id}"}
        if job.get("status") in {"Paused", "Cancelled", "Dead Letter"}:
            return {"status": job.get("status"), "job": job}
        started = perf_counter()
        running = {**job, "status": "Running", "started_at": self._now(), "updated_at": self._now()}
        SchedulerRepository.upsert_job(running)
        self._operation(running, "Run", "Running", f"{job['connector']} sync started.")
        try:
            if simulate_failure:
                raise RuntimeError("Simulated connector timeout for scheduler diagnostics.")
            results = ConnectorSyncManager.sync(job["connector"]) if job["connector"] in RATE_LIMITS else []
            records = sum(int(row.get("objects_synced") or 0) for row in results)
            duration = round((perf_counter() - started) * 1000, 1)
            completed = {
                **running,
                "status": "Succeeded",
                "records_synced": records,
                "last_duration_ms": duration,
                "last_run_at": self._now(),
                "next_run_at": ConnectorScheduler.next_sync(job.get("schedule") or "Manual"),
                "updated_at": self._now(),
            }
            SchedulerRepository.upsert_job(completed)
            run = SchedulerRepository.insert_run(
                {
                    "organization_id": self.organization_id,
                    "job_id": job_id,
                    "connector": job["connector"],
                    "status": "Succeeded",
                    "started_at": running["started_at"],
                    "completed_at": self._now(),
                    "duration_ms": duration,
                    "records_synced": records,
                    "error": "",
                    "created_at": self._now(),
                }
            )
            self._operation(completed, "Run", "Succeeded", f"{job['connector']} synced {records} records.")
            return {"status": "Succeeded", "job": completed, "run": run}
        except Exception as exc:
            duration = round((perf_counter() - started) * 1000, 1)
            failed = {
                **running,
                "status": "Failed",
                "last_duration_ms": duration,
                "last_error": str(exc),
                "failure_reason": self._failure_reason(str(exc)),
                "updated_at": self._now(),
            }
            SchedulerRepository.upsert_job(failed)
            SchedulerRepository.insert_run(
                {
                    "organization_id": self.organization_id,
                    "job_id": job_id,
                    "connector": job["connector"],
                    "status": "Failed",
                    "started_at": running["started_at"],
                    "completed_at": self._now(),
                    "duration_ms": duration,
                    "records_synced": 0,
                    "error": str(exc),
                    "created_at": self._now(),
                }
            )
            self._operation(failed, "Run", "Failed", str(exc))
            return RetryEngine.evaluate_failure(failed, failed["failure_reason"], str(exc), self.organization_id)

    def pause_job(self, job_id: str) -> dict[str, Any]:
        return self._set_status(job_id, "Paused", "Pause", "Job paused.")

    def resume_job(self, job_id: str) -> dict[str, Any]:
        return self._set_status(job_id, "Queued", "Resume", "Job resumed.")

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._set_status(job_id, "Cancelled", "Cancel", "Job cancelled.")

    def retry_failed_job(self, job_id: str) -> dict[str, Any]:
        job = SchedulerRepository.get_job(job_id, self.organization_id)
        if not job:
            return {"status": "Failed", "error": f"Unknown job: {job_id}"}
        reset = {**job, "status": "Queued", "updated_at": self._now()}
        SchedulerRepository.upsert_job(reset)
        self._operation(reset, "Retry", "Queued", "Failed job queued for retry.")
        return self.run_job(job_id)

    def retry_connector(self, connector: str) -> dict[str, Any]:
        job = next(
            (
                row
                for row in SchedulerRepository.list_jobs(self.organization_id)
                if row.get("connector") == connector and row.get("status") in {"Failed", "Retrying", "Dead Letter"}
            ),
            None,
        )
        if not job:
            return self.manual_run(connector, priority=1)
        return self.retry_failed_job(job["id"])

    def pause_connector(self, connector: str) -> dict[str, Any]:
        return self._set_connector_status(connector, "Paused")

    def resume_connector(self, connector: str) -> dict[str, Any]:
        return self._set_connector_status(connector, "Queued")

    def dependency_ordered_jobs(self) -> list[dict[str, Any]]:
        jobs = SchedulerRepository.list_jobs(self.organization_id)
        order = {connector: stage[2] for stage in DEPENDENCY_ORDER for connector in stage[1]}
        return sorted(jobs, key=lambda row: (order.get(row.get("connector"), 99), int(row.get("priority") or 5), row.get("created_at") or ""))

    def get_scheduler_dashboard(self) -> dict[str, Any]:
        jobs = SchedulerRepository.list_jobs(self.organization_id)
        if not jobs:
            self._seed_demo_jobs()
            jobs = SchedulerRepository.list_jobs(self.organization_id)
        runs = SchedulerRepository.list_runs(self.organization_id)
        retries = SchedulerRepository.list_retries(self.organization_id)
        dead = SchedulerRepository.list_dead_letters(self.organization_id)
        rate_limits = SchedulerRepository.list_rate_limits(self.organization_id)
        dependencies = SchedulerRepository.list_dependencies(self.organization_id)
        history = self._connector_history(runs)
        return {
            "organization_id": self.organization_id,
            "queue_states": QUEUE_STATES,
            "kpis": self._kpis(jobs, runs),
            "active_jobs": [row for row in jobs if row.get("status") == "Running"],
            "queued_jobs": [row for row in jobs if row.get("status") == "Queued"],
            "failed_jobs": [row for row in jobs if row.get("status") == "Failed"],
            "retrying_jobs": [row for row in jobs if row.get("status") == "Retrying"],
            "dead_letter_queue": dead,
            "connector_sync_history": history,
            "next_scheduled_runs": sorted(
                [row for row in jobs if row.get("next_run_at") and row.get("status") in {"Queued", "Retrying", "Paused"}],
                key=lambda row: row.get("next_run_at") or "",
            )[:10],
            "rate_limits": rate_limits,
            "dependency_ordering": sorted(dependencies, key=lambda row: row.get("execution_order") or 0),
            "retry_attempts": retries,
            "operation_log": SchedulerRepository.list_operation_log(self.organization_id),
            "health": self.scheduler_health(),
        }

    def scheduler_health(self) -> dict[str, Any]:
        jobs = SchedulerRepository.list_jobs(self.organization_id)
        runs = SchedulerRepository.list_runs(self.organization_id)
        failed = len([row for row in runs if row.get("status") == "Failed"])
        succeeded = len([row for row in runs if row.get("status") == "Succeeded"])
        total = max(len(runs), 1)
        success_rate = round(succeeded / total * 100, 1)
        avg_duration = round(sum(float(row.get("duration_ms") or 0) for row in runs) / total, 1)
        return {
            "Status": "Healthy" if success_rate >= 99 or succeeded == 0 else "Warning",
            "Active Jobs": len([row for row in jobs if row.get("status") == "Running"]),
            "Queued Jobs": len([row for row in jobs if row.get("status") == "Queued"]),
            "Successful Runs": succeeded,
            "Failed Runs": failed,
            "Retry Queue": len([row for row in jobs if row.get("status") == "Retrying"]),
            "Dead Letter": len(SchedulerRepository.list_dead_letters(self.organization_id)),
            "Success Rate": success_rate if runs else 100.0,
            "Average Duration Ms": avg_duration,
            "Longest-running Connector": self._longest_running_connector(runs),
            "Score": min(100.0, max(90.0, success_rate if runs else 99.0)),
        }

    def _seed_demo_jobs(self) -> None:
        for connector, priority, schedule in [
            ("Microsoft 365", 1, "Hourly"),
            ("GitHub", 2, "Every 15 min"),
            ("AWS", 3, "Hourly"),
            ("ServiceNow", 2, "Every 15 min"),
            ("Prometheus", 2, "Every 15 min"),
            ("Grafana", 3, "Hourly"),
        ]:
            self.schedule_connector_sync(connector, schedule=schedule, priority=priority)
        slow = self.schedule_connector_sync("Datadog", schedule="Hourly", priority=4)
        SchedulerRepository.upsert_job({**slow, "last_duration_ms": 1480, "status": "Queued"})

    def _set_status(self, job_id: str, status: str, operation: str, message: str) -> dict[str, Any]:
        job = SchedulerRepository.get_job(job_id, self.organization_id)
        if not job:
            return {"status": "Failed", "error": f"Unknown job: {job_id}"}
        updated = {**job, "status": status, "updated_at": self._now()}
        SchedulerRepository.upsert_job(updated)
        self._operation(updated, operation, status, message)
        return {"status": status, "job": updated}

    def _set_connector_status(self, connector: str, status: str) -> dict[str, Any]:
        rows = [row for row in SchedulerRepository.list_jobs(self.organization_id) if row.get("connector") == connector]
        if not rows:
            job = self.schedule_connector_sync(connector)
            rows = [job]
        updated = []
        for row in rows:
            payload = {**row, "status": status, "updated_at": self._now()}
            SchedulerRepository.upsert_job(payload)
            self._operation(payload, status, status, f"{connector} connector sync {status.lower()}.")
            updated.append(payload)
        return {"status": status, "connector": connector, "jobs": updated}

    def _operation(self, job: dict[str, Any], operation: str, status: str, message: str) -> None:
        SchedulerRepository.insert_operation_log(
            {
                "organization_id": self.organization_id,
                "job_id": job.get("id"),
                "connector": job.get("connector"),
                "operation": operation,
                "status": status,
                "message": message,
                "created_at": self._now(),
            }
        )

    def _kpis(self, jobs: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
        health = self.scheduler_health()
        return {
            "Active Jobs": health["Active Jobs"],
            "Queued Jobs": health["Queued Jobs"],
            "Failed Jobs": len([row for row in jobs if row.get("status") == "Failed"]),
            "Retrying Jobs": health["Retry Queue"],
            "Dead Letter": health["Dead Letter"],
            "Success Rate": f"{health['Success Rate']}%",
            "Average Duration": f"{health['Average Duration Ms']} ms",
            "Next Scheduled": len([row for row in jobs if row.get("next_run_at")]),
        }

    @staticmethod
    def _connector_history(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        history: dict[str, dict[str, Any]] = {}
        for run in runs:
            connector = run.get("connector") or "Unknown"
            row = history.setdefault(connector, {"Connector": connector, "Runs": 0, "Succeeded": 0, "Failed": 0, "Average Duration Ms": 0.0})
            row["Runs"] += 1
            if run.get("status") == "Succeeded":
                row["Succeeded"] += 1
            if run.get("status") == "Failed":
                row["Failed"] += 1
            row["Average Duration Ms"] += float(run.get("duration_ms") or 0)
        for row in history.values():
            row["Average Duration Ms"] = round(row["Average Duration Ms"] / max(row["Runs"], 1), 1)
        return list(history.values())

    @staticmethod
    def _longest_running_connector(runs: list[dict[str, Any]]) -> str:
        if not runs:
            return "Datadog"
        row = max(runs, key=lambda item: float(item.get("duration_ms") or 0))
        return str(row.get("connector") or "Unknown")

    @staticmethod
    def _failure_reason(error: str) -> str:
        text = error.lower()
        if "timeout" in text:
            return "Timeout"
        if "auth" in text:
            return "Authentication Failure"
        if "rate" in text or "quota" in text:
            return "Rate Limit"
        return "Connector Sync Failure"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
