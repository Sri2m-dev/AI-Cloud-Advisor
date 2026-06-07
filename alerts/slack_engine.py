from __future__ import annotations

import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


def send_slack_alert(
    webhook_url: str,
    title: str,
    message: str,
    severity: str = "info",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send an alert to Slack via webhook.

    Args:
        webhook_url: Slack webhook URL (must include /services/...)
        title: Alert title
        message: Alert message
        severity: 'critical', 'warning', 'info' (maps to color)
        details: Optional dict of additional fields

    Returns:
        {"ok": bool, "message": str, "status_code": int}
    """
    if not webhook_url or not webhook_url.startswith("https://"):
        return {
            "ok": False,
            "message": "Invalid webhook URL",
            "status_code": 400,
        }

    severity_colors = {
        "critical": "#d92d20",
        "warning": "#f79009",
        "info": "#0969da",
    }
    color = severity_colors.get(str(severity or "").lower(), "#0969da")

    fields = []
    if details:
        for key, value in details.items():
            fields.append(
                {
                    "title": str(key),
                    "value": str(value),
                    "short": True,
                }
            )

    payload = {
        "attachments": [
            {
                "color": color,
                "title": title,
                "text": message,
                "fields": fields,
                "ts": int(__import__("time").time()),
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            return {
                "ok": True,
                "message": "Slack alert sent",
                "status_code": 200,
            }
        else:
            return {
                "ok": False,
                "message": f"Slack returned {response.status_code}",
                "status_code": response.status_code,
            }
    except Exception as e:
        LOGGER.exception("Slack alert failed: %s", e)
        return {
            "ok": False,
            "message": str(e),
            "status_code": 500,
        }

