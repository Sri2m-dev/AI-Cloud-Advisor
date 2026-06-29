from __future__ import annotations

from typing import Final


RADIUS: Final[dict[str, str]] = {
    "none": "0",
    "xs": "2px",
    "sm": "4px",
    "md": "6px",
    "lg": "8px",
    "pill": "999px",
}

BORDERS: Final[dict[str, str]] = {
    "thin": "1px solid var(--nexora-border)",
    "medium": "1px solid var(--nexora-border-strong)",
    "focus": "1px solid var(--nexora-primary)",
    "transparent": "1px solid transparent",
}


def radius(token: str = "lg") -> str:
    return RADIUS.get(token, RADIUS["lg"])
