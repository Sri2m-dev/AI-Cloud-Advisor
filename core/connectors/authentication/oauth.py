from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OAuthConfig:
    client_id: str
    client_secret_ref: str
    token_url: str
    scopes: tuple[str, ...] = ()
    authorization_url: str = ""

    def masked(self) -> dict:
        return {
            "type": "oauth",
            "client_id": self.client_id,
            "client_secret_ref": self.client_secret_ref,
            "token_url": self.token_url,
            "authorization_url": self.authorization_url,
            "scopes": list(self.scopes),
        }
