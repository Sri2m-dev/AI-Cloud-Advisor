"""
APScheduler Configuration
Simple scheduling for background jobs running on fixed intervals.
Can be used alongside or instead of Celery for development/small deployments.

Jobs:
- Alert checks: every 5 minutes
- Cost data refresh: every 15 minutes
- Forecast refresh: daily
- AI summaries: daily
- SLA escalation: hourly
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = None


def init_scheduler():
    """Initialize and start the background scheduler."""
    global scheduler

    scheduler = BackgroundScheduler()

    # ============= ALERT PROCESSING =============
    # Process alerts every 5 minutes
    scheduler.add_job(
        alert_check_job,
        trigger=IntervalTrigger(minutes=5),
        id="alert_check_5min",
        name="Alert checks every 5 minutes",
        replace_existing=True,
        max_instances=1,
    )

    # ============= COST DATA REFRESH =============
    # Refresh cost data every 15 minutes
    scheduler.add_job(
        refresh_cost_data_job,
        trigger=IntervalTrigger(minutes=15),
        id="cost_refresh_15min",
        name="Cost data refresh every 15 minutes",
        replace_existing=True,
        max_instances=1,
    )

    # ============= SLA ESCALATION =============
    # Check for SLA violations every hour
    scheduler.add_job(
        sla_escalation_job,
        trigger=IntervalTrigger(hours=1),
        id="sla_escalation_hourly",
        name="SLA escalation checks every hour",
        replace_existing=True,
        max_instances=1,
    )

    # ============= DAILY JOBS =============
    # Refresh forecasts daily at 1 AM
    scheduler.add_job(
        forecast_refresh_job,
        trigger=CronTrigger(hour=1, minute=0),
        id="forecast_refresh_daily",
        name="Forecast refresh daily at 1 AM",
        replace_existing=True,
        max_instances=1,
    )

    # Generate AI summaries daily at 6 AM
    scheduler.add_job(
        ai_summary_job,
        trigger=CronTrigger(hour=6, minute=0),
        id="ai_summary_daily",
        name="AI summaries daily at 6 AM",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("✓ APScheduler initialized with 5 jobs")
    return scheduler


# ============= JOB IMPLEMENTATIONS =============


def alert_check_job():
    """Check and process pending alerts every 5 minutes."""
    try:
        from services.alert_processor import process_alerts
        from data.supabase_client import supabase

        logger.info("[scheduler] alert_check_job: Starting...")

        # Check for recent escalations that need alerts
        try:
            response = supabase.table("recommendation_events").select("*").eq("event_type", "escalation").gte("created_at", "now()-5minutes").execute()
            recent_escalations = response.data or []

            if recent_escalations:
                logger.info(f"[scheduler] alert_check_job: Found {len(recent_escalations)} recent escalations")
                result = process_alerts(
                    title="SLA Escalation Alert",
                    message=f"{len(recent_escalations)} recommendations have been escalated due to SLA violations",
                    severity="critical",
                )
                logger.info(f"[scheduler] alert_check_job: Alerts sent - {result}")
            else:
                logger.info("[scheduler] alert_check_job: No recent escalations")

        except Exception as e:
            logger.error(f"[scheduler] alert_check_job: Error processing alerts - {e}")

    except Exception as e:
        logger.error(f"[scheduler] alert_check_job: Failed - {e}")


def refresh_cost_data_job():
    """Refresh cost data from cloud providers every 15 minutes."""
    try:
        logger.info("[scheduler] refresh_cost_data_job: Starting...")

        from services.cost_service import refresh_cost_data

        result = refresh_cost_data()
        logger.info(f"[scheduler] refresh_cost_data_job: Completed - {result}")

    except ImportError:
        logger.warning("[scheduler] refresh_cost_data_job: cost_service not available, skipping")
    except Exception as e:
        logger.error(f"[scheduler] refresh_cost_data_job: Failed - {e}")


def sla_escalation_job():
    """Check for SLA violations and escalate stale approvals every hour."""
    try:
        logger.info("[scheduler] sla_escalation_job: Starting...")

        from services.escalation_service import batch_escalate_stale

        # Escalate stale PENDING_APPROVAL (48h SLA)
        result_pending = batch_escalate_stale(
            workflow_state="PENDING_APPROVAL",
            sla_hours=48,
            actor="scheduler_system",
            dry_run=False,
        )
        logger.info(f"[scheduler] sla_escalation_job: PENDING_APPROVAL - escalated {result_pending.get('escalated_count', 0)}")

        # Escalate stale APPROVED (72h SLA)
        result_approved = batch_escalate_stale(
            workflow_state="APPROVED",
            sla_hours=72,
            actor="scheduler_system",
            dry_run=False,
        )
        logger.info(f"[scheduler] sla_escalation_job: APPROVED - escalated {result_approved.get('escalated_count', 0)}")

    except Exception as e:
        logger.error(f"[scheduler] sla_escalation_job: Failed - {e}")


def forecast_refresh_job():
    """Refresh demand/cost forecasts daily at 1 AM."""
    try:
        logger.info("[scheduler] forecast_refresh_job: Starting...")

        from services.forecast_service import generate_forecasts

        result = generate_forecasts()
        logger.info(f"[scheduler] forecast_refresh_job: Completed - {result}")

    except ImportError:
        logger.warning("[scheduler] forecast_refresh_job: forecast_service not available, skipping")
    except Exception as e:
        logger.error(f"[scheduler] forecast_refresh_job: Failed - {e}")


def ai_summary_job():
    """Generate AI summaries and recommendations daily at 6 AM."""
    try:
        logger.info("[scheduler] ai_summary_job: Starting...")

        from services.ai_recommendation_engine import generate_daily_summary

        result = generate_daily_summary()
        logger.info(f"[scheduler] ai_summary_job: Completed - {result}")

    except ImportError:
        logger.warning("[scheduler] ai_summary_job: AI engine not available, skipping")
    except Exception as e:
        logger.error(f"[scheduler] ai_summary_job: Failed - {e}")


def stop_scheduler():
    """Gracefully stop the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("✓ APScheduler stopped")


if __name__ == "__main__":
    # Test scheduler
    import time

    logging.basicConfig(level=logging.INFO)
    init_scheduler()
    print("Scheduler running. Press Ctrl+C to stop...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_scheduler()

