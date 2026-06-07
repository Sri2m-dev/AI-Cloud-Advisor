from __future__ import annotations

import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


def send_teams_alert(
    webhook_url: str,
    title: str,
    message: str,
    severity: str = "info",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send an alert to Microsoft Teams via webhook.

    Args:
        webhook_url: Teams webhook URL (Incoming Webhook)
        title: Alert title
        message: Alert message
        severity: 'critical', 'warning', 'info'
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
        "critical": "e81123",
        "warning": "ffc000",
        "info": "0078d4",
    }
    color = severity_colors.get(str(severity or "").lower(), "0078d4")

    facts = []
    if details:
        for key, value in details.items():
            facts.append(
                {
                    "name": str(key),
                    "value": str(value),
                }
            )

    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": color,
        "sections": [
            {
                "activityTitle": title,
                "activitySubtitle": f"Severity: {severity.upper()}",
                "text": message,
                "facts": facts,
            }
        ],
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code in {200, 201}:
            return {
                "ok": True,
                "message": "Teams alert sent",
                "status_code": 200,
            }
        else:
            return {
                "ok": False,
                "message": f"Teams returned {response.status_code}",
                "status_code": response.status_code,
            }
    except Exception as e:
        LOGGER.exception("Teams alert failed: %s", e)
        return {
            "ok": False,
            "message": str(e),
            "status_code": 500,
        }

