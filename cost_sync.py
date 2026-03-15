"""Automated background sync for saved cloud accounts."""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database.db import list_cloud_accounts
from services.cloud_account_service import CloudAccountSyncError, sync_cloud_account


LOGGER = logging.getLogger(__name__)
_scheduler = None


def sync_all_cloud_costs():
    LOGGER.info("[Cost Sync] Running at %s", datetime.now())
    accounts = list_cloud_accounts()
    for account in accounts:
        if not account.get("sync_enabled", 1):
            continue
        try:
            sync_cloud_account(account["id"], trigger_type="scheduled")
            LOGGER.info("[Cost Sync] Synced %s account %s", account["provider"], account["account_identifier"])
        except CloudAccountSyncError as exc:
            LOGGER.warning(
                "[Cost Sync] Failed to sync %s account %s: %s",
                account["provider"],
                account["account_identifier"],
                exc,
            )
    LOGGER.info("[Cost Sync] Completed cloud account sync.")


def start_scheduler(interval_hours=24):
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        sync_all_cloud_costs,
        trigger=IntervalTrigger(hours=interval_hours),
        id="cloud-cost-sync",
        replace_existing=True,
        next_run_time=datetime.now(),
    )
    scheduler.start()
    _scheduler = scheduler
    LOGGER.info("[Cost Sync] Scheduler started with %s-hour interval.", interval_hours)
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_scheduler()
    import time

    while True:
        time.sleep(60)
