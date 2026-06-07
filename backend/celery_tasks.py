from backend.celery_app import celery_app
from backend.jobs.tasks import (
    job_alert_engine_hourly,
    job_alert_processor_hourly,
    job_anomaly_scan_hourly,
    job_cost_ingestion_hourly,
    job_escalation_hourly,
    job_kpi_refresh_15m,
    job_optimization_engine_daily,
    job_report_generation_daily,
)


@celery_app.task(name="backend.celery_tasks.job_cost_ingestion_hourly_task")
def job_cost_ingestion_hourly_task() -> None:
    job_cost_ingestion_hourly()


@celery_app.task(name="backend.celery_tasks.job_anomaly_scan_hourly_task")
def job_anomaly_scan_hourly_task() -> None:
    job_anomaly_scan_hourly()


@celery_app.task(name="backend.celery_tasks.job_alert_engine_hourly_task")
def job_alert_engine_hourly_task() -> None:
    job_alert_engine_hourly()


@celery_app.task(name="backend.celery_tasks.job_kpi_refresh_15m_task")
def job_kpi_refresh_15m_task() -> None:
    job_kpi_refresh_15m()


@celery_app.task(name="backend.celery_tasks.job_optimization_engine_daily_task")
def job_optimization_engine_daily_task() -> None:
    job_optimization_engine_daily()


@celery_app.task(name="backend.celery_tasks.job_report_generation_daily_task")
def job_report_generation_daily_task() -> None:
    job_report_generation_daily()


@celery_app.task(name="backend.celery_tasks.job_escalation_hourly_task")
def job_escalation_hourly_task() -> None:
    job_escalation_hourly()


@celery_app.task(name="backend.celery_tasks.job_alert_processor_hourly_task")
def job_alert_processor_hourly_task() -> None:
    job_alert_processor_hourly()

