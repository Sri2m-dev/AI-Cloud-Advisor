import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from api.v1.approvals import router as approvals_router
from backend.jobs.scheduler import stop_scheduler
from backend.middleware.tenant_isolation import TenantIsolationMiddleware
from backend.routes.auth import router as auth_router
from nexora_release import RELEASE_VERSION


@asynccontextmanager
async def lifespan(application):
    startup_jobs()
    try:
        yield
    finally:
        shutdown_jobs()


app = FastAPI(title="Nexora API", version=RELEASE_VERSION, lifespan=lifespan)
app.add_middleware(TenantIsolationMiddleware)

REQUEST_COUNT = Counter(
    "aicloudadvisor_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "aicloudadvisor_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)
APPLICATION_ERRORS = Counter("nexora_application_errors_total", "Unhandled application errors")


def infrastructure_readiness(path=None, *, now=None):
    """Operational availability only; never a G08 authority/qualification PASS."""
    now = time.time() if now is None else now
    try:
        status = json.loads(Path(path or os.environ["NEXORA_READINESS_FILE"]).read_text())
        components = status["components"]
        expected = {"api", "frontend", "redis", "postgres", "auth"}
        if set(components) != expected or any(components[name] is not True for name in expected):
            return False
        age = now - status["observed_at"]
        return 0 <= age <= 120 and status["infrastructure_ready"] is True and status["protected_execution_enabled"] is False
    except (OSError, KeyError, TypeError, ValueError):
        return False


def startup_jobs() -> None:
    if os.getenv("BACKGROUND_JOBS_ENABLED", "false").lower() == "true":
        raise RuntimeError(
            "BACKGROUND_JOBS_ENABLED is not supported by the V1 API route profile"
        )


def shutdown_jobs() -> None:
    stop_scheduler()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    available = infrastructure_readiness()
    return Response(json.dumps({"infrastructure_ready": available, "protected_execution_enabled": False}),
                    status_code=200 if available else 503, media_type="application/json")


@app.middleware("http")
async def capture_metrics(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        APPLICATION_ERRORS.inc()
        raise
    duration = time.perf_counter() - start
    # Route templates bound cardinality and avoid recording caller identifiers.
    path = getattr(request.scope.get("route"), "path", "unmatched")
    REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(
    approvals_router,
    prefix="/api/v1",
    tags=["approvals"],
)
