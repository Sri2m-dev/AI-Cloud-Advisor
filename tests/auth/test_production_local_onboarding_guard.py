from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from config import settings
from services import onboarding_service
from services.onboarding_service import OnboardingError

ROOT = Path(__file__).resolve().parents[2]


def test_production_login_keeps_supabase_sign_in_and_hides_local_onboarding(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    app = AppTest.from_file(str(ROOT / "pages" / "login.py")).run(timeout=10)

    assert not app.exception
    assert [button.label for button in app.button] == ["Login"]
    assert onboarding_service.local_onboarding_allowed() is False


@pytest.mark.parametrize(
    ("handler", "args"),
    [
        (
            onboarding_service.create_organization_and_onboard,
            ("admin@example.com", "Example Org"),
        ),
        (
            onboarding_service.accept_invitation,
            ("unused-token", "member@example.com"),
        ),
    ],
)
def test_production_local_onboarding_handlers_fail_before_database_access(
    monkeypatch, handler, args
):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        onboarding_service,
        "get_db",
        lambda: pytest.fail("production local onboarding must not access SQLite"),
    )

    with pytest.raises(OnboardingError, match="disabled for this authentication mode"):
        handler(*args)


@pytest.mark.parametrize("environment", ["development", "test"])
def test_nonproduction_local_onboarding_remains_available(monkeypatch, environment):
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)

    assert onboarding_service.local_onboarding_allowed() is True


def test_explicit_synthetic_demo_keeps_nonproduction_onboarding(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.delenv("AUTH_MODE", raising=False)
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    assert onboarding_service.local_onboarding_allowed() is True


def test_external_auth_mode_hides_local_onboarding_in_development(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_MODE", "supabase")
    monkeypatch.setenv("SUPABASE_URL", "https://auth.example.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "synthetic-public-key")

    assert onboarding_service.local_onboarding_allowed() is False
