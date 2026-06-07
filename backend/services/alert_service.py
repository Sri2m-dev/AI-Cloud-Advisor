import os
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText

import httpx


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    if not url:
        return {"sent": False, "reason": "Webhook URL not configured"}
    try:
        response = httpx.post(url, json=payload, headers=headers or {}, timeout=15.0)
        response.raise_for_status()
        return {"sent": True, "status_code": response.status_code}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}


def send_email_alert(
    subject: str,
    body: str,
    recipients: list[str],
    attachments: list[dict] | None = None,
) -> dict:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    sender = os.getenv("SMTP_SENDER", smtp_user or "noreply@aicloudadvisor.local")

    if not smtp_host or not recipients:
        return {"sent": False, "reason": "SMTP or recipients not configured"}

    attachments = attachments or []

    if attachments:
        message = EmailMessage()
        message.set_content(body)
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        for item in attachments:
            filename = str(item.get("filename") or "attachment.bin")
            mime_type = str(item.get("mime_type") or "application/octet-stream")
            payload = item.get("content") or b""
            maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
            message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    else:
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(recipients)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.sendmail(sender, recipients, message.as_string())

    return {"sent": True, "recipients": recipients}


def send_slack_alert(webhook_url: str, title: str, message: str, severity: str = "info") -> dict:
    payload = {
        "text": f"*{title}*\nSeverity: {severity}\n{message}",
    }
    return _post_json(webhook_url, payload)


def send_teams_alert(webhook_url: str, title: str, message: str, severity: str = "info") -> dict:
    payload = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": "D92D20" if str(severity).lower() in {"critical", "high"} else "F79009",
        "title": title,
        "text": message,
    }
    return _post_json(webhook_url, payload)


def send_webhook_alert(url: str, title: str, message: str, severity: str = "info", payload: dict | None = None, headers: dict | None = None) -> dict:
    body = {
        "title": title,
        "message": message,
        "severity": severity,
        "payload": payload or {},
    }
    return _post_json(url, body, headers=headers)


def dispatch_alert_channels(alert: dict, config: dict) -> dict:
    title = f"[{alert.get('alert_type', 'alert')}] AI Cloud Advisor"
    message = str(alert.get("message", ""))
    severity = str(alert.get("severity", "info"))
    payload = alert.get("payload") or {}
    channels = config.get("channels") or {}
    results = {}

    email_cfg = channels.get("email") or {}
    if email_cfg.get("enabled"):
        results["email"] = send_email_alert(
            subject=title,
            body=message,
            recipients=[str(item) for item in (email_cfg.get("recipients") or []) if str(item).strip()],
        )

    slack_cfg = channels.get("slack") or {}
    if slack_cfg.get("enabled"):
        results["slack"] = send_slack_alert(slack_cfg.get("webhook_url", ""), title=title, message=message, severity=severity)

    teams_cfg = channels.get("teams") or {}
    if teams_cfg.get("enabled"):
        results["teams"] = send_teams_alert(teams_cfg.get("webhook_url", ""), title=title, message=message, severity=severity)

    webhook_cfg = channels.get("webhook") or {}
    if webhook_cfg.get("enabled"):
        results["webhook"] = send_webhook_alert(
            webhook_cfg.get("url", ""),
            title=title,
            message=message,
            severity=severity,
            payload=payload,
            headers=webhook_cfg.get("headers") or {},
        )

    return results

