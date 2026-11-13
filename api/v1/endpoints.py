"""Compatibility API entry point restricted to authenticated V1 routes."""

from typing import Dict

from fastapi import FastAPI

from api.v1.approvals import router as approvals_router
from backend.middleware.tenant_isolation import TenantIsolationMiddleware
from nexora_release import RELEASE_VERSION

app = FastAPI(
    title="AI Cloud Advisor API",
    description="Authenticated NEXORA V1 customer workflow API",
    version=RELEASE_VERSION,
)
app.add_middleware(TenantIsolationMiddleware)
app.include_router(approvals_router, prefix="/api/v1", tags=["approvals"])


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "healthy"}
