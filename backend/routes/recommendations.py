from typing import Optional

from fastapi import APIRouter, Depends

from backend.security import get_current_user, require_role, tenant_guard
from backend.services.recommendation_service import get_recommendations, run_recommendation_engine

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

