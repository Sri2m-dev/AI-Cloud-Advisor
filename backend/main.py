from fastapi import FastAPI, Request, Response
import os
import time
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from backend.middleware.tenant_isolation import TenantIsolationMiddleware
from backend.jobs.scheduler import start_scheduler, stop_scheduler
from backend.routes.auth import router as auth_router
from backend.routes.alerts import router as alerts_router
from backend.routes.cost import router as cost_router
from backend.routes.governance import router as governance_router
from backend.routes.reports import router as reports_router
from backend.routes.recommendations import router as recommendations_router

app = FastAPI(title="AI Cloud Advisor API", version="1.0.0")
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


@app.on_event("startup")
def startup_jobs() -> None:
	if os.getenv("BACKGROUND_JOBS_ENABLED", "false").lower() == "true":
		start_scheduler()


@app.on_event("shutdown")
def shutdown_jobs() -> None:
	stop_scheduler()


@app.get("/health")
def health():
	return {"status": "ok"}


@app.middleware("http")
async def capture_metrics(request: Request, call_next):
	start = time.perf_counter()
	response = await call_next(request)
	duration = time.perf_counter() - start
	path = request.url.path
	REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
	REQUEST_LATENCY.labels(request.method, path).observe(duration)
	return response


@app.get("/metrics")
def metrics():
	return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(cost_router, prefix="/api/v1", tags=["cost"])
app.include_router(recommendations_router, prefix="/api/v1", tags=["recommendations"])
app.include_router(reports_router, prefix="/api/v1", tags=["reports"])
app.include_router(alerts_router, prefix="/api/v1", tags=["alerts"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(governance_router, prefix="/api/v1", tags=["governance"])

from api.v1.approvals import router as approvals_router

app.include_router(
    approvals_router,
    prefix="/api/v1",
    tags=["approvals"]
)