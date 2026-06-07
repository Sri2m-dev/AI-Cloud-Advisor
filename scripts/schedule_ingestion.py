import os
import subprocess
import time

INTERVAL_MINUTES = int(os.getenv("INGESTION_INTERVAL_MINUTES", "60"))


def run_ingestion_once() -> None:
    subprocess.run(["python", "aws_cost_sync.py"], check=False)
    subprocess.run(["python", "azure_cost_sync.py"], check=False)
    subprocess.run(["python", "gcp_cost_sync.py"], check=False)


if __name__ == "__main__":
    while True:
        run_ingestion_once()
        time.sleep(max(INTERVAL_MINUTES, 1) * 60)

