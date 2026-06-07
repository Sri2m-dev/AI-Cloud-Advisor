from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel

from backend.security import get_current_user, require_role, tenant_guard
from backend.services.alert_service import (
    dispatch_alert_channels,
    send_email_alert,
    send_slack_alert,
    send_teams_alert,
    send_webhook_alert,
)
from backend.services.alerting_engine import (
    evaluate_alerts,
    get_alert_config,
    list_alert_history,
    record_alert_event,
    save_alert_config,
)
from services.alert_processor import (
    process_alerts,
    get_alert_configs,
    execute_email_alert,
    execute_slack_alert,
    execute_teams_alert,
    execute_webhook_alert,
)

router = APIRouter()


class AlertRequest(BaseModel):
    recipients: List[str]
    subject: str
    message: str


class AlertChannelConfig(BaseModel):
    enabled: bool = False
    recipients: List[str] | None = None
    webhook_url: str | None = None
    url: str | None = None
    headers: dict | None = None


class AlertConfigRequest(BaseModel):
    spend_spike_pct: float = 25.0
    idle_vm_min_savings: float = 100.0
    savings_opportunity_threshold: float = 500.0
    governance_score_drop_threshold: float = 10.0
    governance_score_floor: float = 70.0
    cooldown_minutes: int = 180
    channels: dict


class SlackAlertRequest(BaseModel):
    webhook_url: str
    subject: str
    message: str
    severity: str = "info"


class TeamsAlertRequest(BaseModel):
    webhook_url: str
    subject: str
    message: str
    severity: str = "info"


class WebhookAlertRequest(BaseModel):
    url: str
    subject: str
    message: str
    severity: str = "info"
    payload: dict | None = None
    headers: dict | None = None


@router.post("/alerts/email")
def email_alert(
    payload: AlertRequest,
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
):
    subject = f"[{tenant_id}] {payload.subject}"
    result = send_email_alert(subject=subject, body=payload.message, recipients=[str(r) for r in payload.recipients])
    return {"tenant_id": tenant_id, **result}


@router.post("/alerts/slack")
def slack_alert(
    payload: SlackAlertRequest,
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
):
    return {"tenant_id": tenant_id, **send_slack_alert(payload.webhook_url, f"[{tenant_id}] {payload.subject}", payload.message, payload.severity)}


@router.post("/alerts/teams")
def teams_alert(
    payload: TeamsAlertRequest,
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
):
    return {"tenant_id": tenant_id, **send_teams_alert(payload.webhook_url, f"[{tenant_id}] {payload.subject}", payload.message, payload.severity)}


@router.post("/alerts/webhook")
def webhook_alert(
    payload: WebhookAlertRequest,
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
):
    return {
        "tenant_id": tenant_id,
        **send_webhook_alert(payload.url, f"[{tenant_id}] {payload.subject}", payload.message, payload.severity, payload.payload, payload.headers),
    }


@router.get("/alerts/config")
def alert_config(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    return get_alert_config(tenant_id=tenant_id)


@router.put("/alerts/config")
def update_alert_config(
    payload: AlertConfigRequest,
    user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    return save_alert_config(tenant_id=tenant_id, config=payload.model_dump(), updated_by=user.get("username", "api"))


@router.get("/alerts/history")
def alert_history(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager", "Viewer"])),
    tenant_id: str = Depends(tenant_guard),
):
    return {"tenant_id": tenant_id, "items": list_alert_history(tenant_id=tenant_id)}


@router.post("/alerts/run")
def run_alert_engine(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
    tenant_id: str = Depends(tenant_guard),
):
    config = get_alert_config(tenant_id=tenant_id)
    alerts = evaluate_alerts(tenant_id=tenant_id)
    results = []
    for alert in alerts:
        delivery = dispatch_alert_channels(alert, config)
        status = "sent" if any(item.get("sent") for item in delivery.values()) else "pending"
        results.append({"alert": alert, "delivery": delivery, "status": status})
        record_alert_event(
            tenant_id=tenant_id,
            alert_type=str(alert.get("alert_type")),
            severity=str(alert.get("severity", "info")),
            message=str(alert.get("message", "")),
            channels=list(delivery.keys()),
            status=status,
            payload={"alert": alert.get("payload") or {}, "delivery": delivery},
        )
    return {"tenant_id": tenant_id, "count": len(results), "results": results}


# ==================== NEW ALERT PROCESSOR ROUTES ====================


class AlertConfigV2Create(BaseModel):
    name: str
    channel: str  # 'email', 'slack', 'teams', 'webhook'
    active: bool = True
    webhook_url: str | None = None
    recipients: list[str] | None = None
    slack_channel: str | None = None
    include_metadata: bool = True
    custom_payload: dict | None = None


class AlertTestPayloadV2(BaseModel):
    title: str
    message: str
    severity: str = "info"
    config_id: int | None = None


@router.get("/alerts/v2/configs")
def list_alert_configs_v2(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
    active_only: bool = Query(True),
):
    """List alert configurations (new processor)."""
    try:
        configs = get_alert_configs(active_only=active_only, organization_id=tenant_id)
        return {
            "ok": True,
            "configs": configs,
            "total": len(configs),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/v2/configs")
def create_alert_config_v2(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
    payload: AlertConfigV2Create = Body(...),
):
    """Create a new alert configuration (new processor)."""
    from data.supabase_client import supabase
    import datetime

    try:
        config_data = {
            "organization_id": tenant_id,
            "name": payload.name,
            "channel": payload.channel,
            "active": payload.active,
            "webhook_url": payload.webhook_url,
            "recipients": payload.recipients or [],
            "slack_channel": payload.slack_channel or "general",
            "include_metadata": payload.include_metadata,
            "custom_payload": payload.custom_payload or {},
            "created_by": _user.get("username", "api_user"),
            "created_at": datetime.datetime.utcnow().isoformat(),
        }

        response = supabase.table("alert_configs").insert(config_data).execute()
        if response.data:
            return {
                "ok": True,
                "config": response.data[0],
                "message": "Alert config created",
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to create config")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/alerts/v2/configs/{config_id}")
def update_alert_config_v2(
    config_id: int,
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
    payload: AlertConfigV2Create = Body(...),
):
    """Update an alert configuration (new processor)."""
    from data.supabase_client import supabase
    import datetime

    try:
        update_data = {
            "name": payload.name,
            "channel": payload.channel,
            "active": payload.active,
            "webhook_url": payload.webhook_url,
            "recipients": payload.recipients or [],
            "slack_channel": payload.slack_channel or "general",
            "include_metadata": payload.include_metadata,
            "custom_payload": payload.custom_payload or {},
            "updated_at": datetime.datetime.utcnow().isoformat(),
        }

        response = supabase.table("alert_configs").update(update_data).eq("id", config_id).eq("organization_id", tenant_id).execute()
        if response.data:
            return {
                "ok": True,
                "config": response.data[0],
                "message": "Alert config updated",
            }
        else:
            raise HTTPException(status_code=404, detail="Config not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/v2/test")
def test_alert_v2(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
    payload: AlertTestPayloadV2 = Body(...),
):
    """Test an alert by sending it through the specified config."""
    try:
        if payload.config_id:
            # Test specific config
            configs = get_alert_configs(active_only=False, organization_id=tenant_id)
            config = next((c for c in configs if c["id"] == payload.config_id), None)
            if not config:
                raise HTTPException(status_code=404, detail="Config not found")

            channel = config.get("channel")
            if channel == "email":
                result = execute_email_alert(config, payload.title, payload.message, payload.severity)
            elif channel == "slack":
                result = execute_slack_alert(config, payload.title, payload.message, payload.severity)
            elif channel == "teams":
                result = execute_teams_alert(config, payload.title, payload.message, payload.severity)
            elif channel == "webhook":
                result = execute_webhook_alert(config, payload.title, payload.message, payload.severity)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown channel: {channel}")

            return {
                "ok": result.get("ok", False),
                "message": result.get("message"),
                "channel": channel,
            }
        else:
            # Test all configs
            result = process_alerts(
                title=payload.title,
                message=payload.message,
                severity=payload.severity,
                organization_id=tenant_id,
            )
            return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/v2/send")
def send_alert_v2(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin"])),
    tenant_id: str = Depends(tenant_guard),
    payload: AlertTestPayloadV2 = Body(...),
):
    """Manually send an alert across all configured channels."""
    try:
        result = process_alerts(
            title=payload.title,
            message=payload.message,
            severity=payload.severity,
            organization_id=tenant_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/v2/executions")
def list_alert_executions_v2(
    _user=Depends(get_current_user),
    _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "Auditor"])),
    tenant_id: str = Depends(tenant_guard),
    limit: int = Query(50, ge=1, le=500),
    success_only: bool = Query(False),
):
    """List alert execution history."""
    from data.supabase_client import supabase

    try:
        query = supabase.table("alert_executions").select("*").eq("organization_id", tenant_id).order("executed_at", desc=True).limit(limit)
        if success_only:
            query = query.eq("success", True)

        response = query.execute()
        return {
            "ok": True,
            "executions": response.data or [],
            "total": len(response.data or []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

