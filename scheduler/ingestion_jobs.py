import logging
import subprocess

# ---------------------------------------------------
# Logging
# ---------------------------------------------------

logging.basicConfig(
    filename="logs/ingestion_jobs.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------------------------------------------
# Single Cloud Sync Runner
# ---------------------------------------------------

def run_script(script_name: str):

    try:

        logging.info(f"Starting {script_name}")

        subprocess.run(
            ["python", script_name],
            check=True
        )

        logging.info(f"Completed {script_name}")

    except Exception as exc:

        logging.error(f"{script_name} failed: {exc}")


# ---------------------------------------------------
# Main Ingestion Job
# ---------------------------------------------------

def run_ingestion():

    logging.info("Running cloud ingestion pipeline")

    run_script("aws_cost_sync.py")
    run_script("azure_cost_sync.py")
    run_script("gcp_cost_sync.py")

    logging.info("Cloud ingestion pipeline completed")


# ---------------------------------------------------
# Manual Execution
# ---------------------------------------------------

if __name__ == "__main__":
    run_ingestion()

