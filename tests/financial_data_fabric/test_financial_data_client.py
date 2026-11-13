from __future__ import annotations

from types import SimpleNamespace

import pytest

import services.supabase_client as supabase_client


def test_financial_data_client_uses_current_auth_token_and_public_key(monkeypatch):
    calls = {}

    class Postgrest:
        def auth(self, token):
            calls["token"] = token

    client = SimpleNamespace(auth=Postgrest().auth)

    def create_postgrest_client(url, *, headers):
        calls["url"] = url
        calls["key"] = headers["apikey"]
        return client

    monkeypatch.setenv("FINANCIAL_DATA_URL", "http://r5-financial-data-postgrest:3000")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "public-anon-key")
    monkeypatch.setattr(supabase_client, "SyncPostgrestClient", create_postgrest_client)
    auth_client = SimpleNamespace(
        auth=SimpleNamespace(
            get_session=lambda: SimpleNamespace(access_token="verified-user-token")
        )
    )

    assert supabase_client.create_user_financial_data_client(auth_client) is client
    assert calls == {
        "url": "http://r5-financial-data-postgrest:3000",
        "key": "public-anon-key",
        "token": "verified-user-token",
    }


def test_financial_data_client_reads_public_key_from_secret_file(monkeypatch, tmp_path):
    calls = {}
    key_file = tmp_path / "supabase-anon-key"
    key_file.write_text("public-anon-key", encoding="utf-8")

    class Postgrest:
        def auth(self, token):
            calls["token"] = token

    client = SimpleNamespace(auth=Postgrest().auth)

    def create_postgrest_client(url, *, headers):
        calls["url"] = url
        calls["key"] = headers["apikey"]
        return client

    monkeypatch.setenv("FINANCIAL_DATA_URL", "http://r5-financial-data-postgrest:3000")
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY_FILE", str(key_file))
    monkeypatch.setattr(supabase_client, "SyncPostgrestClient", create_postgrest_client)
    auth_client = SimpleNamespace(
        auth=SimpleNamespace(
            get_session=lambda: SimpleNamespace(access_token="verified-user-token")
        )
    )

    assert supabase_client.create_user_financial_data_client(auth_client) is client
    assert calls == {
        "url": "http://r5-financial-data-postgrest:3000",
        "key": "public-anon-key",
        "token": "verified-user-token",
    }


@pytest.mark.parametrize(
    ("auth_client", "data_url", "anon_key", "message"),
    [
        (None, "http://r5-financial-data-postgrest:3000", "public", "authenticated"),
        (
            SimpleNamespace(
                auth=SimpleNamespace(get_session=lambda: SimpleNamespace(access_token=None))
            ),
            "http://r5-financial-data-postgrest:3000",
            "public",
            "access token",
        ),
        (
            SimpleNamespace(
                auth=SimpleNamespace(
                    get_session=lambda: SimpleNamespace(access_token="user-token")
                )
            ),
            "http://unexpected.example",
            "public",
            "endpoint",
        ),
        (
            SimpleNamespace(
                auth=SimpleNamespace(
                    get_session=lambda: SimpleNamespace(access_token="user-token")
                )
            ),
            "http://r5-financial-data-postgrest:3000",
            "",
            "SUPABASE_ANON_KEY",
        ),
    ],
)
def test_financial_data_client_fails_closed(
    monkeypatch, auth_client, data_url, anon_key, message
):
    monkeypatch.setenv("FINANCIAL_DATA_URL", data_url)
    monkeypatch.setenv("SUPABASE_ANON_KEY", anon_key)
    monkeypatch.setenv("SUPABASE_ANON_KEY_FILE", "")

    with pytest.raises((PermissionError, RuntimeError), match=message):
        supabase_client.create_user_financial_data_client(auth_client)
