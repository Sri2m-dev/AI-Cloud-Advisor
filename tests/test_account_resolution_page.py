from streamlit.testing.v1 import AppTest


def test_account_resolution_page_loads_without_traceback():
    app = AppTest.from_file("pages/account_resolution.py", default_timeout=30)
    session = {
        "authenticated": True,
        "auth_backend": "local",
        "user": "admin@company.com",
        "user_id": "p42-certification",
        "email": "admin@company.com",
        "role": "super_admin",
        "organization_id": "71cf875a-2103-47a0-8886-41a97c5750ec",
        "organization_name": "Default Org",
        "authorized_organization_ids": ["71cf875a-2103-47a0-8886-41a97c5750ec"],
        "permissions": [],
    }
    for key, value in session.items():
        app.session_state[key] = value
    app.run()
    assert not app.exception
    assert any("Account Resolution" in title.value for title in app.title)
