"""
Approval API Endpoints
Handles approval workflow operations via REST API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel

from services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


# ==============================================================================
# Request/Response Models
# ==============================================================================

class CreateApprovalRequest(BaseModel):
    """Request model for creating an approval"""
    title: str
    description: Optional[str] = None
    type: Optional[str] = "general"
    priority: Optional[str] = "medium"
    assigned_to: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ApprovalResponse(BaseModel):
    """Response model for approval data"""
    id: str
    title: str
    description: Optional[str] = None
    type: str
    priority: str
    status: str
    created_by: str
    created_at: str
    updated_at: str


class ApproveRequestBody(BaseModel):
    """Request body for approving an approval"""
    approved_by: str
    comments: Optional[str] = None


class RejectRequestBody(BaseModel):
    """Request body for rejecting an approval"""
    rejected_by: str
    reason: Optional[str] = None


class EscalateRequestBody(BaseModel):
    """Request body for escalating an approval"""
    escalated_by: str
    escalate_to: str
    reason: Optional[str] = None


class ApprovalListResponse(BaseModel):
    """Response model for approval list"""
    total: int
    approvals: list


# ==============================================================================
# API Endpoints
# ==============================================================================

@router.post("/create")
def create_approval(
    request: CreateApprovalRequest,
    created_by: str = Query(..., description="User ID creating the approval"),
    org_id: str = Query(..., description="Organization ID")
) -> Dict[str, Any]:
    """
    Create a new approval request.
    
    **Parameters:**
    - `title`: Approval title
    - `description`: Detailed description (optional)
    - `type`: Type of approval (general, cost, security, etc.)
    - `priority`: Priority level (low, medium, high)
    - `assigned_to`: Assign to a specific user (optional)
    - `created_by`: User creating the approval
    - `org_id`: Organization ID
    
    **Returns:**
    Created approval record with ID
    """
    try:
        approval_data = request.dict(exclude_none=True)
        result = approval_service.create_approval(approval_data, created_by, org_id)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {"success": True, "approval": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating approval: {str(e)}")


@router.get("/list")
def list_approvals(
    org_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500)
) -> ApprovalListResponse:
    """
    List approvals with optional filtering.
    
    **Query Parameters:**
    - `org_id`: Filter by organization ID
    - `status`: Filter by status (PENDING, APPROVED, REJECTED, ESCALATED)
    - `assigned_to`: Filter by assigned user
    - `limit`: Maximum number of results (default: 100, max: 500)
    
    **Returns:**
    List of approval records matching filters
    """
    try:
        approvals = approval_service.get_approvals(
            org_id=org_id,
            status=status,
            assigned_to=assigned_to,
            limit=limit
        )
        
        return ApprovalListResponse(
            total=len(approvals),
            approvals=approvals
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching approvals: {str(e)}")


@router.get("/{approval_id}")
def get_approval(approval_id: str) -> Dict[str, Any]:
    """
    Retrieve a single approval by ID.
    
    **Parameters:**
    - `approval_id`: The approval ID to retrieve
    
    **Returns:**
    Approval record or 404 if not found
    """
    try:
        approval = approval_service.get_approval_by_id(approval_id)
        
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        
        return {"success": True, "approval": approval}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching approval: {str(e)}")


@router.post("/{approval_id}/approve")
def approve(
    approval_id: str,
    request: ApproveRequestBody
) -> Dict[str, Any]:
    """
    Approve an approval request.
    
    **Parameters:**
    - `approval_id`: The approval ID to approve
    - `approved_by`: User ID of the approver
    - `comments`: Optional approval comments
    
    **Returns:**
    Updated approval record with APPROVED status
    """
    try:
        result = approval_service.approve_request(
            approval_id=approval_id,
            approved_by=request.approved_by,
            comments=request.comments
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {"success": True, "approval": result}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error approving request: {str(e)}")


@router.post("/{approval_id}/reject")
def reject(
    approval_id: str,
    request: RejectRequestBody
) -> Dict[str, Any]:
    """
    Reject an approval request.
    
    **Parameters:**
    - `approval_id`: The approval ID to reject
    - `rejected_by`: User ID of the rejector
    - `reason`: Reason for rejection (optional)
    
    **Returns:**
    Updated approval record with REJECTED status
    """
    try:
        result = approval_service.reject_request(
            approval_id=approval_id,
            rejected_by=request.rejected_by,
            reason=request.reason
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {"success": True, "approval": result}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rejecting request: {str(e)}")


@router.post("/{approval_id}/escalate")
def escalate(
    approval_id: str,
    request: EscalateRequestBody
) -> Dict[str, Any]:
    """
    Escalate an approval request to a higher level.
    
    **Parameters:**
    - `approval_id`: The approval ID to escalate
    - `escalated_by`: User ID of the escalator
    - `escalate_to`: User ID to escalate to
    - `reason`: Reason for escalation (optional)
    
    **Returns:**
    Updated approval record with ESCALATED status
    """
    try:
        result = approval_service.escalate_request(
            approval_id=approval_id,
            escalated_by=request.escalated_by,
            escalate_to=request.escalate_to,
            reason=request.reason
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {"success": True, "approval": result}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error escalating request: {str(e)}")


@router.get("/{approval_id}/history")
def get_approval_history(approval_id: str) -> Dict[str, Any]:
    """
    Get the approval history and audit trail.
    
    **Parameters:**
    - `approval_id`: The approval ID
    
    **Returns:**
    List of audit log entries for the approval
    """
    try:
        # TODO: Implement full audit trail retrieval
        # For now, return a placeholder
        return {
            "success": True,
            "approval_id": approval_id,
            "history": []
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching approval history: {str(e)}")


@router.get("/metrics/queue")
def get_queue_metrics() -> Dict[str, Any]:
    """
    Get approval queue metrics.
    
    **Returns:**
    High-level metrics about pending, approved, and rejected approvals
    """
    try:
        metrics = approval_service.get_approval_queue_metrics()
        return {
            "success": True,
            "metrics": metrics
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")


@router.get("/workflow/transitions")
def get_workflow_transitions() -> Dict[str, Any]:
    """
    Get workflow state transitions.
    
    **Returns:**
    List of possible workflow transitions and state machine definition
    """
    try:
        transitions = approval_service.get_workflow_transitions()
        return {
            "success": True,
            "transitions": transitions
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching transitions: {str(e)}")


@router.get("/dashboard/snapshot")
def get_approval_center_snapshot(
    username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """
    Get approval center dashboard snapshot.
    
    **Query Parameters:**
    - `username`: Filter approvals for a specific user (optional)
    
    **Returns:**
    Aggregated approval metrics and lists for dashboard display
    """
    try:
        snapshot = approval_service.get_approval_center_snapshot(username)
        return {
            "success": True,
            "snapshot": snapshot
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting snapshot: {str(e)}")
