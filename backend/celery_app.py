import os

from celery import Celery

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
    beat_schedule={
        "cost-ingestion-hourly": {
            "task": "backend.celery_tasks.job_cost_ingestion_hourly_task",
            "schedule": 3600.0,
        },
        "anomaly-scan-hourly": {
            "task": "backend.celery_tasks.job_anomaly_scan_hourly_task",
            "schedule": 3600.0,
        },
        "alert-engine-hourly": {
            "task": "backend.celery_tasks.job_alert_engine_hourly_task",
            "schedule": 3600.0,
        },
        "kpi-refresh-15m": {
            "task": "backend.celery_tasks.job_kpi_refresh_15m_task",
            "schedule": 900.0,
        },
        "optimization-daily": {
            "task": "backend.celery_tasks.job_optimization_engine_daily_task",
            "schedule": 86400.0,
        },
        "report-generation-daily": {
            "task": "backend.celery_tasks.job_report_generation_daily_task",
            "schedule": 86400.0,
        },
    },
)

celery_app.autodiscover_tasks(["backend"])

