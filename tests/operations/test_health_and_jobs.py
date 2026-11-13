import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from deploy.operations import monitor
from backend.celery_app import PERIODIC_JOBS, periodic_schedule
from backend.main import infrastructure_readiness


def test_external_probes_disabled_is_not_ready_or_qualified():
    status=monitor.collect(env={},now=100,probe=lambda url:True,
                           disk_usage=lambda p:SimpleNamespace(total=100,free=50),
                           redis_probe=lambda:True,pg_probe=lambda cfg:pytest.fail("no external connection"))
    assert status["components"]["postgres"] is False and status["components"]["auth"] is False
    assert status["infrastructure_ready"] is False and status["protected_execution_enabled"] is False
    assert "nexora_dependency_up" in monitor.metrics(status)


def test_dependency_failure_storage_and_backup_staleness_are_visible(monkeypatch):
    monkeypatch.setattr(monitor.Path,"read_text",lambda p:json.dumps({"last_success":1,"last_attempt_success":False}))
    status=monitor.collect(env={},now=100000,probe=lambda url:False,
                           disk_usage=lambda p:SimpleNamespace(total=100,free=1),redis_probe=lambda:False)
    assert status["storage"]["evidence"]["free_ratio"]==0.01
    assert status["backup_last_attempt_success"] is False
    assert "nexora_backup_last_success_timestamp 1" in monitor.metrics(status)
    assert "nexora_probe_observed_timestamp 100000" in monitor.metrics(status)


def test_readiness_requires_recent_backup_even_when_all_dependencies_are_available(monkeypatch):
    def read(path):
        if path.name=="pg_monitor": return json.dumps({"sslmode":"verify-full"})
        return json.dumps({"last_success":99,"last_attempt_success":True})
    monkeypatch.setattr(monitor.Path,"read_text",read)
    status=monitor.collect(env={"NEXORA_EXTERNAL_PROBES_ENABLED":"true","SUPABASE_URL":"https://example.invalid"},
                           now=100,probe=lambda url:True,disk_usage=lambda p:SimpleNamespace(total=100,free=50),
                           pg_probe=lambda cfg:True,redis_probe=lambda:True)
    assert status["infrastructure_ready"] is True and status["protected_execution_enabled"] is False


def test_postgres_probe_refuses_unverified_tls_before_connection():
    with pytest.raises(ValueError): monitor.postgres_probe({"sslmode":"require"})


def ready_status():
    return {"observed_at":100,"components":dict.fromkeys(["api","frontend","redis","postgres","auth"],True),
            "infrastructure_ready":True,"protected_execution_enabled":False}


@pytest.mark.parametrize("change", [{"observed_at":-100},{"observed_at":200},{"protected_execution_enabled":True},
                                   {"infrastructure_ready":False},{"components":{}}])
def test_readiness_rejects_stale_future_incomplete_or_permission_claim(tmp_path,change):
    path=tmp_path/"status.json";path.write_text(json.dumps(ready_status()|change))
    assert infrastructure_readiness(path,now=100) is False


def test_readiness_is_infrastructure_only_and_missing_is_unavailable(tmp_path):
    assert infrastructure_readiness(tmp_path/"absent",now=100) is False
    path=tmp_path/"status.json";path.write_text(json.dumps(ready_status()))
    assert infrastructure_readiness(path,now=100) is True


def test_all_nine_jobs_have_one_explicit_scheduler_and_default_to_off():
    assert len(PERIODIC_JOBS)==9 and periodic_schedule({})=={}
    for env in [{"NEXORA_SCHEDULED_JOBS_ENABLED":"true"},
                {"NEXORA_SCHEDULED_JOBS_ENABLED":"true","NEXORA_JOB_SCHEDULER":"celery"}]:
        with pytest.raises(RuntimeError): periodic_schedule(env)
    schedule=periodic_schedule({"NEXORA_SCHEDULED_JOBS_ENABLED":"true","NEXORA_JOB_SCHEDULER":"celery",
                                "NEXORA_ENABLED_PERIODIC_JOBS":"kpi-refresh-15m"})
    assert list(schedule)==["kpi-refresh-15m"]


def test_v1_profile_never_schedules_legacy_jobs():
    schedule = periodic_schedule({
        "NEXORA_PRODUCT_PROFILE": "V1",
        "NEXORA_SCHEDULED_JOBS_ENABLED": "true",
        "NEXORA_JOB_SCHEDULER": "celery",
        "NEXORA_ENABLED_PERIODIC_JOBS": "kpi-refresh-15m",
    })
    assert schedule == {}


def test_api_scheduler_cannot_duplicate_production_beat(monkeypatch):
    from backend.jobs.scheduler import start_scheduler
    monkeypatch.setenv("ENVIRONMENT","production")
    with pytest.raises(RuntimeError,match="Celery Beat"): start_scheduler()


def test_disabled_or_stale_queued_task_is_denied_before_work(monkeypatch):
    from backend import celery_tasks
    monkeypatch.setenv("ENVIRONMENT","production")
    monkeypatch.setenv("NEXORA_SCHEDULED_JOBS_ENABLED","false")
    monkeypatch.setattr(celery_tasks,"job_kpi_refresh_15m",lambda:pytest.fail("work must not run"))
    with pytest.raises(RuntimeError): celery_tasks.job_kpi_refresh_15m_task.run()


def test_only_explicitly_selected_queued_task_can_reach_job_body(monkeypatch):
    from backend import celery_tasks
    monkeypatch.setenv("ENVIRONMENT","production")
    monkeypatch.setenv("NEXORA_SCHEDULED_JOBS_ENABLED","true")
    monkeypatch.setenv("NEXORA_JOB_SCHEDULER","celery")
    monkeypatch.setenv("NEXORA_ENABLED_PERIODIC_JOBS","kpi-refresh-15m")
    calls=[]
    monkeypatch.setattr(celery_tasks,"job_kpi_refresh_15m",lambda:calls.append("synthetic"))
    celery_tasks.job_kpi_refresh_15m_task.run()
    assert calls==["synthetic"]


@pytest.mark.parametrize("environment", ["development", "production"])
def test_v1_profile_rejects_queued_legacy_task_even_when_allowlisted(
    environment, monkeypatch
):
    from backend import celery_tasks
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("NEXORA_PRODUCT_PROFILE", "V1")
    monkeypatch.setenv("NEXORA_SCHEDULED_JOBS_ENABLED", "true")
    monkeypatch.setenv("NEXORA_JOB_SCHEDULER", "celery")
    monkeypatch.setenv("NEXORA_ENABLED_PERIODIC_JOBS", "kpi-refresh-15m")
    monkeypatch.setattr(
        celery_tasks,
        "job_kpi_refresh_15m",
        lambda: pytest.fail("work must not run"),
    )
    with pytest.raises(RuntimeError, match="excluded from the V1 profile"):
        celery_tasks.job_kpi_refresh_15m_task.run()


def test_health_is_liveness_and_missing_readiness_returns_503(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    monkeypatch.delenv("NEXORA_READINESS_FILE",raising=False)
    monkeypatch.setenv("BACKGROUND_JOBS_ENABLED","false")
    with TestClient(app) as client:
        assert client.get("/health").status_code==200
        response=client.get("/ready")
        assert response.status_code==503 and response.json()["protected_execution_enabled"] is False
