"""
API v1 Endpoints (Track 4)
- Governance APIs
- FinOps APIs
- SaaS APIs
- Approval APIs
"""
from typing import Dict

from fastapi import FastAPI

from api.v1.approvals import router as approvals_router
from api.v1.finops import router as finops_router
from api.v1.governance import router as governance_router
from api.v1.saas import router as saas_router
from nexora_release import RELEASE_VERSION

app = FastAPI(
    title="AI Cloud Advisor API",
    description="Multi-cloud governance, FinOps, and SaaS management API",
    version=RELEASE_VERSION
)

# Register routers
app.include_router(governance_router)
app.include_router(finops_router)
app.include_router(saas_router)
app.include_router(approvals_router)


# --- Health Check ---
@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}


# To run: uvicorn api.v1.endpoints:app --reload

