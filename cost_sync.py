# cost_sync.py
"""
Automated daily cost data sync for AWS, Azure, and GCP.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import logging

# Import cost fetchers (implement these if not present)
from services.aws_cost import get_aws_cost

from services.azure_connector import get_azure_cost
from services.gcp_connector import get_gcp_cost


# Import your database save function
from database.db import save_cost_data

def sync_all_cloud_costs():
    logging.info(f"[Cost Sync] Running at {datetime.now()}")
    aws_cost = get_aws_cost()
    save_cost_data('aws', aws_cost)
    azure_cost = get_azure_cost()
    save_cost_data('azure', azure_cost)
    gcp_cost = get_gcp_cost()
    save_cost_data('gcp', gcp_cost)
    logging.info("[Cost Sync] Completed cloud cost sync.")


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(sync_all_cloud_costs, 'interval', days=1, next_run_time=datetime.now())
    scheduler.start()
    logging.info("[Cost Sync] Scheduler started.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_scheduler()
    # Keep the script running
    import time
    while True:
        time.sleep(60)
