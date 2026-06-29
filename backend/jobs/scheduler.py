import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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

LOGGER = logging.getLogger("background-jobs")
SCHEDULER = BackgroundScheduler(timezone=os.getenv("SCHEDULER_TZ", "UTC"))
_STARTED = False


def _register_jobs() -> None:
    SCHEDULER.add_job(
        job_cost_ingestion_hourly,
        trigger=IntervalTrigger(hours=1),
        id="cost_ingestion_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_discovery_scheduler_hourly,
        trigger=IntervalTrigger(hours=1),
        id="discovery_scheduler_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_anomaly_scan_hourly,
        trigger=IntervalTrigger(hours=1),
        id="anomaly_scan_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_alert_engine_hourly,
        trigger=IntervalTrigger(hours=1),
        id="alert_engine_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_escalation_hourly,
        trigger=IntervalTrigger(hours=1),
        id="escalation_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_alert_processor_hourly,
        trigger=IntervalTrigger(hours=1),
        id="alert_processor_hourly",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_optimization_engine_daily,
        trigger=CronTrigger(hour=2, minute=0),
        id="optimization_engine_daily",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_kpi_refresh_15m,
        trigger=IntervalTrigger(minutes=15),
        id="kpi_refresh_15m",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    SCHEDULER.add_job(
        job_report_generation_daily,
        trigger=CronTrigger(hour=3, minute=0),
        id="report_generation_daily",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


def start_scheduler() -> None:
    global _STARTED
    if _STARTED:
        return
    _register_jobs()
    SCHEDULER.start()
    _STARTED = True
    LOGGER.info("Background scheduler started with %s jobs", len(SCHEDULER.get_jobs()))


def stop_scheduler() -> None:
    global _STARTED
    if not _STARTED:
        return
    SCHEDULER.shutdown(wait=False)
    _STARTED = False
    LOGGER.info("Background scheduler stopped")

