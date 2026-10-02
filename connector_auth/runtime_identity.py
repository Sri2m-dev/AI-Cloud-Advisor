"""Provider-neutral runtime identity token sources."""

from __future__ import annotations

from pathlib import Path


class WebIdentityTokenFileSource:
    """Reads a short-lived web identity token from a runtime-projected file."""

    def __init__(self, token_file: str):
        self.token_file = Path(token_file)

    def token(self) -> str:
        token = self.token_file.read_text(encoding="utf-8").strip()

        if not token:
            raise ValueError(
                "Web identity token file contains no token."
            )

        return token