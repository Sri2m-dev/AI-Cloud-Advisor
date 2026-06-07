from core.rules_engine.engine import RuleEngine
from core.workflows.automation import AutoRoutingEngine
from core.workflows.sla_notifications import SLANotificationHandler
from services.notification_service import NotificationService

def process_approval(approval, recipients):
    actions = RuleEngine.evaluate(approval)
    for action in actions:
        if action == 'require_finance_approval':
            NotificationService.send_email('Finance Approval Required', 'Approval needs finance review.', recipients)
        elif action == 'require_security_team':
            NotificationService.send_teams('Security Review Required', recipients)
        elif action == 'auto_generate_recommendation':
            NotificationService.send_in_app('Auto-recommendation generated for idle resource.', recipients)
    # Example: auto-routing
    route = AutoRoutingEngine.route(approval)
    NotificationService.send_in_app(f'Approval routed to {route}', recipients)
    # Example: SLA escalation notification
    if 'sla_status' in approval and approval['sla_status'] != 'ok':
        SLANotificationHandler.notify_escalation(approval, approval['sla_status'], recipients)

