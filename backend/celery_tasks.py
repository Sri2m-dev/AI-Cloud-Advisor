from backend.celery_app import celery_app
import os
from backend.celery_app import periodic_schedule
from backend.jobs.tasks import (
    job_alert_engine_hourly,
    job_alert_processor_hourly,
    job_anomaly_scan_hourly,
    job_cost_ingestion_hourly,
    job_discovery_scheduler_hourly,
    job_escalation_hourly,
    job_kpi_refresh_15m,
    job_optimization_engine_daily,
    job_report_generation_daily,
)


def require_enabled_task(task_name):
    if os.getenv("NEXORA_PRODUCT_PROFILE", "").strip().lower() == "v1":
        raise RuntimeError("Legacy queued tasks are excluded from the V1 profile")
    if os.getenv("ENVIRONMENT", "").lower() in {"prod", "production"}:
        enabled = {entry["task"] for entry in periodic_schedule(os.environ).values()}
        if task_name not in enabled:
            raise RuntimeError("Unqualified or disabled queued task refused")


@celery_app.task(name="backend.celery_tasks.job_discovery_scheduler_hourly_task")
def job_discovery_scheduler_hourly_task() -> None:
    require_enabled_task("backend.celery_tasks.job_discovery_scheduler_hourly_task")
    job_discovery_scheduler_hourly()


@celery_app.task(name="backend.celery_tasks.job_cost_ingestion_hourly_task")
def job_cost_ingestion_hourly_task() -> None:
    require_enabled_task("backend.celery_tasks.job_cost_ingestion_hourly_task")
    job_cost_ingestion_hourly()


@celery_app.task(name="backend.celery_tasks.job_anomaly_scan_hourly_task")
def job_anomaly_scan_hourly_task() -> None:
    require_enabled_task("backend.celery_tasks.job_anomaly_scan_hourly_task")
    job_anomaly_scan_hourly()


@celery_app.task(name="backend.celery_tasks.job_alert_engine_hourly_task")
def job_alert_engine_hourly_task() -> None:
    require_enabled_task("backend.celery_tasks.job_alert_engine_hourly_task")
    job_alert_engine_hourly()


@celery_app.task(name="backend.celery_tasks.job_kpi_refresh_15m_task")
def job_kpi_refresh_15m_task() -> None:
    require_enabled_task("backend.celery_tasks.job_kpi_refresh_15m_task")
    job_kpi_refresh_15m()


@celery_app.task(name="backend.celery_tasks.job_optimization_engine_daily_task")
def job_optimization_engine_daily_task() -> None:
    require_enabled_task("backend.celery_tasks.job_optimization_engine_daily_task")
    job_optimization_engine_daily()


@celery_app.task(name="backend.celery_tasks.job_report_generation_daily_task")
def job_report_generation_daily_task() -> None:
    require_enabled_task("backend.celery_tasks.job_report_generation_daily_task")
    job_report_generation_daily()


@celery_app.task(name="backend.celery_tasks.job_escalation_hourly_task")
def job_escalation_hourly_task() -> None:
    require_enabled_task("backend.celery_tasks.job_escalation_hourly_task")
    job_escalation_hourly()


@celery_app.task(name="backend.celery_tasks.job_alert_processor_hourly_task")
def job_alert_processor_hourly_task() -> None:
    require_enabled_task("backend.celery_tasks.job_alert_processor_hourly_task")
    job_alert_processor_hourly()

