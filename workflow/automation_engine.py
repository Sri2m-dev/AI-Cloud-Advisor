"""
Workflow Automation Engine (Track 3)
- SLA Engine: Escalation based on pending time
- Notification integration: Email, Teams, Slack, In-app
- Rule Engine: Custom business rules
"""
import datetime
from typing import List, Dict, Callable, Any

# Notification stubs (to be integrated with real engines)
def send_email(to, subject, body):
    print(f"[EMAIL] To: {to} | Subject: {subject} | Body: {body}")

def send_teams(to, message):
    print(f"[TEAMS] To: {to} | Message: {message}")

def send_slack(to, message):
    print(f"[SLACK] To: {to} | Message: {message}")

def send_in_app(user, message):
    print(f"[IN-APP] User: {user} | Message: {message}")

# SLA Escalation Engine
SLA_ESCALATION_RULES = [
    (24, 'manager'),
    (48, 'leadership'),
    (72, 'critical'),
]

def check_sla_escalation(pending_hours: int) -> str:
    for hours, level in reversed(SLA_ESCALATION_RULES):
        if pending_hours >= hours:
            return level
    return None

# Rule Engine
RULES: List[Dict[str, Any]] = [
    {
        'condition': lambda ticket: ticket.get('spend_risk', False),
        'action': lambda ticket: send_email('finance@company.com', 'High Spend Risk', f"Ticket {ticket['id']} requires finance approval."),
    },
    {
        'condition': lambda ticket: ticket.get('security_risk', False),
        'action': lambda ticket: send_email('security@company.com', 'Security Risk', f"Ticket {ticket['id']} requires security team review."),
    },
    {
        'condition': lambda ticket: ticket.get('idle_resource', False),
        'action': lambda ticket: send_in_app(ticket['owner'], f"Resource {ticket['id']} is idle. Auto recommendation triggered."),
    },
]

def process_ticket(ticket: Dict[str, Any]):
    # SLA Escalation
    pending_hours = ticket.get('pending_hours', 0)
    escalation = check_sla_escalation(pending_hours)
    if escalation == 'manager':
        send_email(ticket['manager'], 'SLA Escalation: 24h', f"Ticket {ticket['id']} pending 24h.")
    elif escalation == 'leadership':
        send_email(ticket['leadership'], 'SLA Escalation: 48h', f"Ticket {ticket['id']} pending 48h.")
    elif escalation == 'critical':
        send_email('critical@company.com', 'SLA Critical Breach: 72h', f"Ticket {ticket['id']} pending 72h! Immediate action required.")
    # Rule Engine
    for rule in RULES:
        if rule['condition'](ticket):
            rule['action'](ticket)

# Example usage
def example():
    ticket = {
        'id': 101,
        'pending_hours': 50,
        'manager': 'manager@company.com',
        'leadership': 'leadership@company.com',
        'spend_risk': True,
        'security_risk': False,
        'idle_resource': False,
        'owner': 'user1',
    }
    process_ticket(ticket)

if __name__ == "__main__":
    example()

