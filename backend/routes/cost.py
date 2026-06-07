from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends

from backend.security import get_current_user, require_role, tenant_guard
from backend.services.cost_service import fetch_cost_data

router = APIRouter()


@router.get("/cost")
def get_cost(
    cloud: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager", "Viewer"])),
    tenant_id: str = Depends(tenant_guard),
):
    return fetch_cost_data(
        tenant_id=tenant_id,
        cloud=cloud,
        start_date=start_date,
        end_date=end_date,
        requested_by=user.get("username", "api"),
    )

