from __future__ import annotations

import logging
from typing import Any

from data.supabase_client import supabase
from alerts.email_engine import send_email_alert
from alerts.slack_engine import send_slack_alert
from alerts.teams_engine import send_teams_alert
from alerts.webhook_engine import send_webhook_alert, build_generic_alert_payload
from services.audit_service import log_alert_triggered

LOGGER = logging.getLogger(__name__)


def get_alert_configs(
    active_only: bool = True,
    channel: str | None = None,
    organization_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve alert configurations from database.

    Args:
        active_only: Only return active configs
        channel: Filter by channel ('email', 'slack', 'teams', 'webhook')

    Returns:
        List of alert config dictionaries
    """
    try:
        query = supabase.table("alert_configs").select("*")
        if active_only:
            query = query.eq("active", True)
        if channel:
            query = query.eq("channel", channel)
        if organization_id:
            query = query.eq("organization_id", organization_id)

        response = query.execute()
        return response.data or []
    except Exception as e:
        LOGGER.exception("Failed to retrieve alert configs: %s", e)
        return []


def record_alert_execution(
    config_id: int,
    channel: str,
    title: str,
    message: str,
    severity: str,
    success: bool,
    error_message: str | None = None,
    organization_id: str | None = None,
) -> bool:
    """Record alert execution result to database."""
    try:
        execution_data = {
            "organization_id": organization_id,
            "config_id": config_id,
            "channel": channel,
            "title": title,
            "message": message,
            "severity": severity,
            "success": success,
            "error_message": error_message,
            "executed_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
        response = supabase.table("alert_executions").insert(execution_data).execute()
        if response.data:
            execution = response.data[0]
            log_alert_triggered(
                alert_id=execution.get("id") or config_id,
                triggered_by="alert_processor",
                org_id=execution.get("organization_id") or 1,
                title=title,
                severity=severity,
                channel=channel,
                config_id=config_id,
                success=success,
                error_message=error_message,
            )
        return bool(response.data)
    except Exception as e:
        LOGGER.exception("Failed to record alert execution: %s", e)
        return False


def execute_email_alert(config: dict[str, Any], title: str, message: str, severity: str) -> dict[str, Any]:
    """Execute email alert based on config."""
    recipients = config.get("recipients") or []
    if not recipients:
        return {
            "ok": False,
            "message": "No recipients configured",
        }

    html_body = None
    if config.get("html_template"):
        html_body = config.get("html_template").format(title=title, message=message)

    result = send_email_alert(
        to_address=recipients,
        subject=title,
        message=message,
        html_body=html_body,
        severity=severity,
    )

    record_alert_execution(
        config.get("id"),
        "email",
        title,
        message,
        severity,
        result.get("ok", False),
        result.get("message") if not result.get("ok") else None,
        organization_id=config.get("organization_id"),
    )

    return result


def execute_slack_alert(config: dict[str, Any], title: str, message: str, severity: str) -> dict[str, Any]:
    """Execute Slack alert based on config."""
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return {
            "ok": False,
            "message": "No webhook URL configured",
        }

    details = {}
    if config.get("include_metadata"):
        details["Channel"] = config.get("slack_channel", "general")
        details["Config"] = config.get("name")

    result = send_slack_alert(
        webhook_url=webhook_url,
        title=title,
        message=message,
        severity=severity,
        details=details,
    )

    record_alert_execution(
        config.get("id"),
        "slack",
        title,
        message,
        severity,
        result.get("ok", False),
        result.get("message") if not result.get("ok") else None,
        organization_id=config.get("organization_id"),
    )

    return result


def execute_teams_alert(config: dict[str, Any], title: str, message: str, severity: str) -> dict[str, Any]:
    """Execute Teams alert based on config."""
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return {
            "ok": False,
            "message": "No webhook URL configured",
        }

    details = {}
    if config.get("include_metadata"):
        details["Config"] = config.get("name")

    result = send_teams_alert(
        webhook_url=webhook_url,
        title=title,
        message=message,
        severity=severity,
        details=details,
    )

    record_alert_execution(
        config.get("id"),
        "teams",
        title,
        message,
        severity,
        result.get("ok", False),
        result.get("message") if not result.get("ok") else None,
        organization_id=config.get("organization_id"),
    )

    return result


def execute_webhook_alert(config: dict[str, Any], title: str, message: str, severity: str) -> dict[str, Any]:
    """Execute generic webhook alert based on config."""
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        return {
            "ok": False,
            "message": "No webhook URL configured",
        }

    payload = build_generic_alert_payload(
        title=title,
        message=message,
        severity=severity,
        source=config.get("name", "cloud-advisor"),
        details=config.get("custom_payload", {}),
    )

    auth_header = config.get("auth_header")
    result = send_webhook_alert(
        webhook_url=webhook_url,
        payload=payload,
        auth_header=auth_header,
    )

    record_alert_execution(
        config.get("id"),
        "webhook",
        title,
        message,
        severity,
        result.get("ok", False),
        result.get("message") if not result.get("ok") else None,
        organization_id=config.get("organization_id"),
    )

    return result


def process_alerts(
    title: str,
    message: str,
    severity: str = "info",
    channels: list[str] | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """
    Process and send alerts across configured channels.

    Args:
        title: Alert title
        message: Alert message
        severity: 'critical', 'warning', 'info'
        channels: Filter to specific channels; if None, all active configs are used

    Returns:
        {
            "ok": bool,
            "total_sent": int,
            "total_failed": int,
            "by_channel": {channel: {success_count, failed_count}},
            "results": [execution results],
        }
    """
    results = []
    by_channel = {}

    try:
        configs = get_alert_configs(active_only=True, organization_id=organization_id)

        if channels:
            configs = [c for c in configs if c.get("channel") in channels]

        if not configs:
            LOGGER.warning("No active alert configs found")
            return {
                "ok": True,
                "total_sent": 0,
                "total_failed": 0,
                "by_channel": {},
                "results": [],
            }

        for config in configs:
            channel = config.get("channel", "unknown")
            if channel not in by_channel:
                by_channel[channel] = {"success": 0, "failed": 0}

            try:
                if channel == "email":
                    result = execute_email_alert(config, title, message, severity)
                elif channel == "slack":
                    result = execute_slack_alert(config, title, message, severity)
                elif channel == "teams":
                    result = execute_teams_alert(config, title, message, severity)
                elif channel == "webhook":
                    result = execute_webhook_alert(config, title, message, severity)
                else:
                    result = {"ok": False, "message": f"Unknown channel: {channel}"}

                result["config_id"] = config.get("id")
                result["channel"] = channel
                results.append(result)

                if result.get("ok"):
                    by_channel[channel]["success"] += 1
                else:
                    by_channel[channel]["failed"] += 1

            except Exception as e:
                LOGGER.exception("Failed to execute alert for config %d (%s): %s", config.get("id"), channel, e)
                by_channel[channel]["failed"] += 1
                results.append(
                    {
                        "ok": False,
                        "message": str(e),
                        "config_id": config.get("id"),
                        "channel": channel,
                    }
                )

        total_sent = sum(ch["success"] for ch in by_channel.values())
        total_failed = sum(ch["failed"] for ch in by_channel.values())

        return {
            "ok": True,
            "total_sent": total_sent,
            "total_failed": total_failed,
            "by_channel": by_channel,
            "results": results,
        }

    except Exception as e:
        LOGGER.exception("Alert processing failed: %s", e)
        return {
            "ok": False,
            "total_sent": 0,
            "total_failed": 0,
            "by_channel": {},
            "error": str(e),
        }

