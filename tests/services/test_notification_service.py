import pytest
from services.notification_service import NotificationService

def test_send_email():
    assert NotificationService.send_email('Test', 'Body', ['user@example.com'])

def test_send_slack():
    assert NotificationService.send_slack('Slack message', ['user1'])

def test_send_teams():
    assert NotificationService.send_teams('Teams message', ['user2'])

def test_send_in_app():
    assert NotificationService.send_in_app('In-app alert', ['user3'])

