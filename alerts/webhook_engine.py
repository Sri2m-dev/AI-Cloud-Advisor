from __future__ import annotations

import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


def send_webhook_alert(
    webhook_url: str,
    payload: dict[str, Any],
    auth_header: str | None = None,
) -> dict[str, Any]:
    """
    Send an alert to a generic webhook endpoint.

    Args:
        webhook_url: Target webhook URL
        payload: JSON payload to send
        auth_header: Optional Authorization header value (e.g., "Bearer TOKEN")

    Returns:
        {"ok": bool, "message": str, "status_code": int}
    """
    if not webhook_url or not webhook_url.startswith("https://"):
        return {
            "ok": False,
            "message": "Invalid webhook URL",
            "status_code": 400,
        }

    headers = {
        "Content-Type": "application/json",
    }
    if auth_header:
        headers["Authorization"] = auth_header

    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        if response.status_code in {200, 201, 202}:
            return {
                "ok": True,
                "message": "Webhook alert sent",
                "status_code": response.status_code,
            }
        else:
            return {
                "ok": False,
                "message": f"Webhook returned {response.status_code}: {response.text[:200]}",
                "status_code": response.status_code,
            }
    except Exception as e:
        LOGGER.exception("Webhook alert failed: %s", e)
        return {
            "ok": False,
            "message": str(e),
            "status_code": 500,
        }


def build_generic_alert_payload(
    title: str,
    message: str,
    severity: str = "info",
    source: str = "cloud-advisor",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a generic alert payload for custom webhooks."""
    return {
        "title": title,
        "message": message,
        "severity": severity,
        "source": source,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        "details": details or {},
    }

