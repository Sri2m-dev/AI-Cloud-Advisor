from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from connectors.common.tenant_guard import resolve_organization_id
from repositories.scheduler_repository import SchedulerRepository


class RetryEngine:
    DEFAULT_MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 30
    MAX_BACKOFF_SECONDS = 900

    @staticmethod
    def evaluate_failure(
        job: dict[str, Any],
        failure_reason: str,
        last_error: str,
        organization_id: str | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id or job.get("organization_id"))
        retry_count = int(job.get("retry_count") or 0) + 1
        limit = int(max_retries or job.get("max_retries") or RetryEngine.DEFAULT_MAX_RETRIES)
        if retry_count > limit:
            return RetryEngine.move_to_dead_letter(job, failure_reason, last_error, retry_count, org_id)
        retry = {
            "organization_id": org_id,
            "job_id": job.get("id"),
            "connector": job.get("connector"),
            "retry_count": retry_count,
            "failure_reason": failure_reason,
            "last_error": last_error,
            "next_retry_at": RetryEngine.next_retry_at(retry_count, str(job.get("id") or "")),
            "status": "Retrying",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        SchedulerRepository.insert_retry(retry)
        updated = {
            **job,
            "organization_id": org_id,
            "status": "Retrying",
            "retry_count": retry_count,
            "last_error": last_error,
            "failure_reason": failure_reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        SchedulerRepository.upsert_job(updated)
        return {"status": "Retrying", "retry": retry, "job": updated}

    @staticmethod
    def next_retry_at(retry_count: int, seed: str = "") -> str:
        jitter = RetryEngine.jitter_seconds(seed, retry_count)
        delay = min(RetryEngine.BASE_BACKOFF_SECONDS * (2 ** max(retry_count - 1, 0)) + jitter, RetryEngine.MAX_BACKOFF_SECONDS)
        return (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()

    @staticmethod
    def jitter_seconds(seed: str, retry_count: int) -> int:
        digest = hashlib.sha256(f"{seed}:{retry_count}".encode()).hexdigest()
        return int(digest[:2], 16) % 17

    @staticmethod
    def move_to_dead_letter(
        job: dict[str, Any],
        failure_reason: str,
        last_error: str,
        retry_count: int,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        org_id = resolve_organization_id(organization_id or job.get("organization_id"))
        dead_letter = {
            "organization_id": org_id,
            "job_id": job.get("id"),
            "connector": job.get("connector"),
            "failure_reason": failure_reason,
            "retry_count": retry_count,
            "last_error": last_error,
            "recommended_action": RetryEngine.recommended_action(str(job.get("connector") or ""), failure_reason),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        SchedulerRepository.insert_dead_letter(dead_letter)
        updated = {
            **job,
            "organization_id": org_id,
            "status": "Dead Letter",
            "retry_count": retry_count,
            "last_error": last_error,
            "failure_reason": failure_reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        SchedulerRepository.upsert_job(updated)
        SchedulerRepository.insert_operation_log(
            {
                "organization_id": org_id,
                "job_id": job.get("id"),
                "connector": job.get("connector"),
                "operation": "Dead Letter",
                "status": "Escalated",
                "message": dead_letter["recommended_action"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return {"status": "Dead Letter", "dead_letter": dead_letter, "job": updated}

    @staticmethod
    def recommended_action(connector: str, failure_reason: str) -> str:
        reason = failure_reason.lower()
        if "auth" in reason or "credential" in reason:
            return f"Validate {connector} credentials, rotate token if expired, then retry sync."
        if "rate" in reason or "quota" in reason or "throttle" in reason:
            return f"Reduce {connector} concurrency, wait for quota recovery, then retry sync."
        if "timeout" in reason:
            return f"Increase {connector} sync timeout and split the sync into smaller batches."
        return f"Review {connector} connector logs, validate permissions, and rerun certification before retry."
