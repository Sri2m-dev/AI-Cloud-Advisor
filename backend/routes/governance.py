from fastapi import APIRouter, Depends, Query

from backend.security import get_current_user, require_role, tenant_guard
from backend.services.governance_service import get_governance_summary
from services.escalation_service import batch_escalate_stale, get_aging_summary, get_escalation_report

router = APIRouter()


@router.get("/governance/summary")
def governance_summary(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "Auditor"])),
    tenant_id: str = Depends(tenant_guard),
):
    return get_governance_summary(tenant_id=tenant_id)


@router.get("/escalations/aging-summary")
def escalations_aging_summary(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "Auditor"])),
):
    """Get summary of recommendations by age and SLA violations."""
    return get_aging_summary()


@router.get("/escalations/report")
def escalations_report(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "Auditor"])),
    days: int = Query(7, ge=1, le=90),
):
    """Get escalation activity report for the last N days."""
    return get_escalation_report(days=days)


@router.post("/escalations/trigger")
def escalations_trigger(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    workflow_state: str = Query("PENDING_APPROVAL"),
    dry_run: bool = Query(False),
):
    """Manually trigger escalation check for a specific workflow state."""
    result = batch_escalate_stale(
        workflow_state=workflow_state,
        actor=_user.get("username", "api_user"),
        dry_run=dry_run,
    )
    return result

