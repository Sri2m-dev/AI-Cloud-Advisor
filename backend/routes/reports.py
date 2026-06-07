from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from backend.security import get_current_user, require_role, tenant_guard
from backend.services.report_service import (
    build_executive_pdf,
    get_report_distribution_list,
    list_report_history,
    record_report_history,
    save_report_distribution_list,
    send_executive_report_email,
)

router = APIRouter()


class ReportEmailRequest(BaseModel):
    recipients: list[str]


class ReportRecipientsRequest(BaseModel):
    recipients: list[str]
    active: bool = True


@router.get("/reports/executive.pdf")
def executive_report(
    user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "Viewer"])),
    tenant_id: str = Depends(tenant_guard),
):
    pdf_bytes = build_executive_pdf(tenant_id=tenant_id, requested_by=user.get("username", "api"))
    record_report_history(
        tenant_id=tenant_id,
        report_name="executive_pdf",
        requested_by=user.get("username", "api"),
        delivery_channel="download",
        status="generated",
        file_name=f"executive-report-{tenant_id}.pdf",
    )
    headers = {"Content-Disposition": f'attachment; filename="executive-report-{tenant_id}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.post("/reports/executive/email")
def executive_report_email(
    payload: ReportEmailRequest,
    user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    result = send_executive_report_email(
        tenant_id=tenant_id,
        recipients=payload.recipients,
        requested_by=user.get("username", "api"),
    )
    return {"tenant_id": tenant_id, **result}


@router.get("/reports/history")
def report_history(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "Viewer", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    return {"tenant_id": tenant_id, "items": list_report_history(tenant_id=tenant_id)}


@router.get("/reports/recipients")
def report_recipients(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    return get_report_distribution_list(tenant_id=tenant_id)


@router.put("/reports/recipients")
def update_report_recipients(
    payload: ReportRecipientsRequest,
    user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    return save_report_distribution_list(
        tenant_id=tenant_id,
        recipients=payload.recipients,
        updated_by=user.get("username", "api"),
        active=payload.active,
    )

