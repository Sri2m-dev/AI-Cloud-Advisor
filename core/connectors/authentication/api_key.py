from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApiKeyAuth:
    key_name: str
    secret_ref: str
    location: str = "header"

    def masked(self) -> dict[str, str]:
        return {"type": "api_key", "key_name": self.key_name, "location": self.location, "secret_ref": self.secret_ref}
