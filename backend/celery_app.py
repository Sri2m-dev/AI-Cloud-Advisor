import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "ai_cloud_advisor",
    broker=os.getenv("CELERY_BROKER_URL", REDIS_URL),
    backend=os.getenv("CELERY_RESULT_BACKEND", REDIS_URL),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=os.getenv("SCHEDULER_TZ", "UTC"),
    enable_utc=True,
    task_default_queue="nexora-qualified",
    worker_prefetch_multiplier=1,

)

PERIODIC_JOBS = {
    "cost-ingestion-hourly": {"task": "backend.celery_tasks.job_cost_ingestion_hourly_task", "schedule": 3600.0},
    "discovery-hourly": {"task": "backend.celery_tasks.job_discovery_scheduler_hourly_task", "schedule": 3600.0},
    "anomaly-scan-hourly": {"task": "backend.celery_tasks.job_anomaly_scan_hourly_task", "schedule": 3600.0},
    "alert-engine-hourly": {"task": "backend.celery_tasks.job_alert_engine_hourly_task", "schedule": 3600.0},
    "escalation-hourly": {"task": "backend.celery_tasks.job_escalation_hourly_task", "schedule": 3600.0},
    "alert-processor-hourly": {"task": "backend.celery_tasks.job_alert_processor_hourly_task", "schedule": 3600.0},
    "kpi-refresh-15m": {"task": "backend.celery_tasks.job_kpi_refresh_15m_task", "schedule": 900.0},
    "optimization-daily": {"task": "backend.celery_tasks.job_optimization_engine_daily_task", "schedule": crontab(hour=2, minute=0)},
    "report-generation-daily": {"task": "backend.celery_tasks.job_report_generation_daily_task", "schedule": crontab(hour=3, minute=0)},
}


def periodic_schedule(environment):
    if environment.get("NEXORA_PRODUCT_PROFILE", "").strip().lower() == "v1":
        return {}
    if environment.get("NEXORA_SCHEDULED_JOBS_ENABLED", "false") != "true":
        return {}
    if environment.get("NEXORA_JOB_SCHEDULER") != "celery":
        raise RuntimeError("Celery Beat must be the sole application scheduler")
    selected = environment.get("NEXORA_ENABLED_PERIODIC_JOBS", "").split(",")
    if not all(name in PERIODIC_JOBS for name in selected) or len(set(selected)) != len(selected):
        raise RuntimeError("An explicit unique qualified job allowlist is required")
    return {name: PERIODIC_JOBS[name] for name in selected}


celery_app.conf.beat_schedule = periodic_schedule(os.environ)

celery_app.autodiscover_tasks(["backend"])

