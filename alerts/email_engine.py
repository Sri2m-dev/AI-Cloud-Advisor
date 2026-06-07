from __future__ import annotations

import logging
import os
from typing import Any

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

LOGGER = logging.getLogger(__name__)

# Configuration from environment or defaults
SMTP_SERVER = os.getenv("ALERT_SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("ALERT_SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("ALERT_SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("ALERT_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("ALERT_SMTP_FROM", "alerts@cloud-advisor.ai")


def send_email_alert(
    to_address: str | list[str],
    subject: str,
    message: str,
    html_body: str | None = None,
    severity: str = "info",
) -> dict[str, Any]:
    """
    Send an alert via email.

    Args:
        to_address: Recipient email(s)
        subject: Email subject
        message: Plain text message
        html_body: Optional HTML body (overrides plain text)
        severity: 'critical', 'warning', 'info'

    Returns:
        {"ok": bool, "message": str, "recipients": int}
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        LOGGER.warning("Email alerts not configured (missing SMTP credentials)")
        return {
            "ok": False,
            "message": "Email alerts not configured",
            "recipients": 0,
        }

    recipients = [to_address] if isinstance(to_address, str) else to_address
    if not recipients:
        return {
            "ok": False,
            "message": "No recipients",
            "recipients": 0,
        }

    severity_prefix = {
        "critical": "[CRITICAL]",
        "warning": "[WARNING]",
        "info": "[INFO]",
    }
    prefix = severity_prefix.get(str(severity or "").lower(), "[INFO]")
    final_subject = f"{prefix} {subject}"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = final_subject
        msg["From"] = SMTP_FROM
        msg["To"] = ", ".join(recipients)

        part1 = MIMEText(message, "plain")
        msg.attach(part1)

        if html_body:
            part2 = MIMEText(html_body, "html")
            msg.attach(part2)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, recipients, msg.as_string())

        LOGGER.info("Email alert sent to %d recipients", len(recipients))
        return {
            "ok": True,
            "message": "Email alert sent",
            "recipients": len(recipients),
        }

    except Exception as e:
        LOGGER.exception("Email alert failed: %s", e)
        return {
            "ok": False,
            "message": str(e),
            "recipients": 0,
        }

