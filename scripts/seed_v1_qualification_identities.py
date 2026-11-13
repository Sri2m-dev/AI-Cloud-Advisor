"""Seed synthetic Supabase users and tenant profiles in the isolated M4 target."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ORGANIZATIONS = {
    "customer-a": {
        "id": str(uuid5(NAMESPACE_URL, "nexora-v1-qualification:customer-a")),
        "name": "Synthetic Customer A",
        "status": "active",
    },
    "customer-b": {
        "id": str(uuid5(NAMESPACE_URL, "nexora-v1-qualification:customer-b")),
        "name": "Synthetic Customer B",
        "status": "active",
    },
}
IDENTITIES = {
    "customer-a": ("customer-a", "client_admin"),
    "finance-a": ("customer-a", "finance"),
    "cio-a": ("customer-a", "cio"),
    "executive-a": ("customer-a", "executive"),
    "auditor-a": ("customer-a", "auditor"),
    "customer-b": ("customer-b", "client_admin"),
}


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _service_token(secret: str) -> str:
    now = int(time.time())
    header = _b64url(b'{"alg":"HS256","typ":"JWT"}')
    claims = _b64url(
        json.dumps(
            {
                "iss": "supabase",
                "aud": "authenticated",
                "role": "service_role",
                "iat": now,
                "exp": now + 300,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{header}.{claims}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{header}.{claims}.{_b64url(signature)}"


def _request(
    url: str,
    *,
    token: str,
    anon_key: str,
    method: str = "GET",
    body: dict | list | None = None,
    prefer: str | None = None,
):
    headers = {"apikey": anon_key, "Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"qualification identity API returned HTTP {error.code}") from None
    return json.loads(result) if result else None


def main() -> None:
    auth_url = os.environ["QUAL_AUTH_URL"].rstrip("/")
    rest_url = os.environ["QUAL_REST_URL"].rstrip("/")
    jwt_secret = os.environ["JWT_SECRET"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]
    credential_path = Path(os.environ["QUAL_CUSTOMER_CREDENTIALS_FILE"])
    credentials = json.loads(credential_path.read_text(encoding="utf-8"))
    if set(credentials) != set(IDENTITIES):
        raise RuntimeError("credential file must define the six synthetic qualification accounts")
    admin_token = _service_token(jwt_secret)
    users_response = _request(
        f"{auth_url}/admin/users?page=1&per_page=1000",
        token=admin_token,
        anon_key=anon_key,
    )
    existing = {
        str(user.get("email", "")).casefold(): user
        for user in users_response.get("users", [])
    }

    profile_rows = []
    for account, (organization_key, role) in IDENTITIES.items():
        email = str(credentials[account]["email"]).strip().casefold()
        password = str(credentials[account]["password"])
        if not email or len(password) < 16:
            raise RuntimeError("synthetic account credentials are invalid")
        user = existing.get(email)
        if user is None:
            user = _request(
                f"{auth_url}/admin/users",
                token=admin_token,
                anon_key=anon_key,
                method="POST",
                body={"email": email, "password": password, "email_confirm": True},
            )
        else:
            user = _request(
                f"{auth_url}/admin/users/{user['id']}",
                token=admin_token,
                anon_key=anon_key,
                method="PUT",
                body={"password": password, "email_confirm": True},
            )
            user["id"] = existing[email]["id"]
        user_id = str(user.get("id") or "")
        if not user_id:
            raise RuntimeError("Auth did not return a synthetic user identifier")
        _request(
            f"{auth_url}/token?grant_type=password",
            token=anon_key,
            anon_key=anon_key,
            method="POST",
            body={"email": email, "password": password},
        )
        profile_rows.append(
            {
                "auth_user_id": user_id,
                "email": email,
                "org_id": ORGANIZATIONS[organization_key]["id"],
                "role": role,
                "permissions": [],
            }
        )

    service_key = _service_token(jwt_secret)
    organizations = list(ORGANIZATIONS.values())
    _request(
        f"{rest_url}/organizations?on_conflict=id",
        token=service_key,
        anon_key=anon_key,
        method="POST",
        body=organizations,
        prefer="resolution=merge-duplicates,return=minimal",
    )
    _request(
        f"{rest_url}/users?on_conflict=auth_user_id",
        token=service_key,
        anon_key=anon_key,
        method="POST",
        body=profile_rows,
        prefer="resolution=merge-duplicates,return=minimal",
    )
    print("Seeded six synthetic Auth accounts across two isolated tenant organizations.")


if __name__ == "__main__":
    main()
