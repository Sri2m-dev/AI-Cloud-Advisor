from typing import Dict, Any
import time
import threading

import logging
from typing import Optional

# Simple in-memory metrics store (replace with Prometheus/OpenTelemetry for production)
METRICS = {
    "api_latency": [],
    "dashboard_load_time": [],
    "failed_workflows": [],
    "query_performance": [],
    "ingestion_failures": [],
    "user_activity": [],
}

def track_api_latency(endpoint: str, latency: float):
    METRICS["api_latency"].append({"endpoint": endpoint, "latency": latency, "ts": time.time()})

def track_dashboard_load(page: str, load_time: float):
    METRICS["dashboard_load_time"].append({"page": page, "load_time": load_time, "ts": time.time()})

def track_failed_workflow(workflow: str, reason: str):
    METRICS["failed_workflows"].append({"workflow": workflow, "reason": reason, "ts": time.time()})

def track_query_performance(query: str, duration: float, success: bool):
    METRICS["query_performance"].append({"query": query, "duration": duration, "success": success, "ts": time.time()})

def track_ingestion_failure(source: str, error: str):
    METRICS["ingestion_failures"].append({"source": source, "error": error, "ts": time.time()})

def track_user_activity(user_id: str, action: str, details: Optional[dict] = None):
    METRICS["user_activity"].append({"user_id": user_id, "action": action, "details": details or {}, "ts": time.time()})

# Example: log to file or stdout for now
logging.basicConfig(level=logging.INFO)

def log_metric(category: str, data: dict):
    logging.info(f"[TELEMETRY] {category}: {data}")

