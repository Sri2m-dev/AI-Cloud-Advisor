from typing import Dict, Any, List
from services.notification_service import NotificationService

class SLANotificationHandler:
    @staticmethod
    def notify_escalation(approval: Dict[str, Any], escalation: str, recipients: List[str]):
        subject = f"Approval Escalation: {escalation.replace('_', ' ').title()}"
        message = f"Approval {approval.get('id', '')} has breached SLA: {escalation}"
        if escalation == 'manager_escalation':
            NotificationService.send_email(subject, message, recipients)
            NotificationService.send_in_app(message, recipients)
        elif escalation == 'leadership_escalation':
            NotificationService.send_email(subject, message, recipients)
            NotificationService.send_slack(message, recipients)
            NotificationService.send_teams(message, recipients)
        elif escalation == 'auto_close_or_escalate':
            NotificationService.send_email(subject, message, recipients)
            NotificationService.send_in_app(message, recipients)
            NotificationService.send_slack(message, recipients)
            NotificationService.send_teams(message, recipients)
        else:
            NotificationService.send_in_app(message, recipients)

