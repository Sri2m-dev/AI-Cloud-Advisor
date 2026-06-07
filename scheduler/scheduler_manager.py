from apscheduler.schedulers.background import BackgroundScheduler
from scheduler.recommendation_jobs import run_recommendations
from scheduler.ingestion_jobs import run_ingestion

scheduler = BackgroundScheduler()

scheduler.add_job(
    run_recommendations,
    trigger="interval",
    minutes=1
)

scheduler.add_job(
    run_ingestion,
    trigger="interval",
    minutes=1
)

scheduler.start()

print("Scheduler started successfully")

try:
    import time

    while True:
        time.sleep(60)

except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()

