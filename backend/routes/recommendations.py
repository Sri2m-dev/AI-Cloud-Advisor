from typing import Optional

from fastapi import APIRouter, Depends

from backend.security import get_current_user, require_role, tenant_guard
# Resolve service dependencies only after the route authentication dependencies.
def get_recommendations(*args, **kwargs):
    from backend.services.recommendation_service import get_recommendations as implementation
    return implementation(*args, **kwargs)

def run_recommendation_engine(*args, **kwargs):
    from backend.services.recommendation_service import run_recommendation_engine as implementation
    return implementation(*args, **kwargs)


router = APIRouter()


@router.get("/recommendations")
def list_recommendations(
    status: Optional[str] = None,
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager", "Viewer"])),
    tenant_id: str = Depends(tenant_guard),
):
    rows = get_recommendations(tenant_id=tenant_id, status=status)
    return {"tenant_id": tenant_id, "count": len(rows), "data": rows}


@router.post("/recommendations/run")
def trigger_recommendation_run(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    return run_recommendation_engine(tenant_id=tenant_id)

