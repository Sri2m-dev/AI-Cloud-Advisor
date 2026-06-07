import logging
import signal
import time

from backend.jobs.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)


def _shutdown(*_args):
    stop_scheduler()
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    start_scheduler()
    while True:
        time.sleep(60)

