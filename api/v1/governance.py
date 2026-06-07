from fastapi import APIRouter, HTTPException
from services import approval_service

router = APIRouter()

@router.get('/approvals')
def get_approvals(org_id: str):
    resp = approval_service.get_pending_approvals(org_id)
    if not resp.success:
        raise HTTPException(status_code=400, detail=resp.message)
    return resp

@router.post('/approve')
def approve(approval_id: str, user_id: str, user_role: str):
    resp = approval_service.approve_request(approval_id, user_id, user_role=user_role)
    if not resp.success:
        raise HTTPException(status_code=400, detail=resp.message)
    return resp

@router.post('/reject')
def reject(approval_id: str, user_id: str, user_role: str, reason: str = ""):
    resp = approval_service.reject_request(approval_id, user_id, reason=reason, user_role=user_role)
    if not resp.success:
        raise HTTPException(status_code=400, detail=resp.message)
    return resp

