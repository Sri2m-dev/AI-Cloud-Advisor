from views import onboarding as onboarding_module
from views import ui_helpers as ui_helpers_module


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def markdown(self, *_args, **_kwargs):
        return None


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self._button_returns = {}

    def markdown(self, *_args, **_kwargs):
        return None

    def success(self, *_args, **_kwargs):
        return None

    def columns(self, n):
        count = n if isinstance(n, int) else len(n)
        return [_FakeColumn() for _ in range(count)]

    def button(self, _label, key=None, **_kwargs):
        return bool(self._button_returns.get(key, False))

    def rerun(self):
        raise RuntimeError("rerun-called")


def test_render_empty_state_cta_path_returns_true(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st._button_returns["empty_cta_test"] = True
    monkeypatch.setattr(ui_helpers_module, "st", fake_st)

    clicked = ui_helpers_module.render_empty_state(
        icon="📊",
        title="No data",
        message="Upload data to continue.",
        cta_label="Upload",
        cta_key="empty_cta_test",
    )

    assert clicked is True


def test_onboarding_finish_cta_marks_complete(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.session_state.update(
        {
            "username": "demo-user",
            "onboarding_step": 4,
            "onboard_tz_value": "UTC",
            "onboard_currency_value": "USD ($)",
            "onboard_budget_value": 10000,
            "onboard_provider_value": "AWS",
        }
    )
    fake_st._button_returns["onboard_finish"] = True

    marked = {"username": None}

    def _mark_complete(username):
        marked["username"] = username

    monkeypatch.setattr(onboarding_module, "st", fake_st)
    monkeypatch.setattr(onboarding_module, "mark_onboarding_complete", _mark_complete)

    try:
        onboarding_module.render_onboarding_wizard()
    except RuntimeError as exc:
        assert str(exc) == "rerun-called"

    assert marked["username"] == "demo-user"
    assert "onboarding_step" not in fake_st.session_state
