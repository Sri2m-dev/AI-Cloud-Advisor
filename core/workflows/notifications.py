from typing import List, Dict, Any

class NotificationChannel:
    TEAMS = 'teams'
    SLACK = 'slack'
    EMAIL = 'email'
    IN_APP = 'in_app'

class Notifier:
    @staticmethod
    def send(channel: str, message: str, recipients: List[str], payload: Dict[str, Any] = None):
        # TODO: Integrate with actual notification services
        print(f"[NOTIFY] {channel}: {message} to {recipients} | {payload or {}}")

