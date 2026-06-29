from __future__ import annotations

from typing import Final


SPACING: Final[dict[str, str]] = {
    "0": "0",
    "1": "0.25rem",
    "2": "0.5rem",
    "3": "0.75rem",
    "4": "1rem",
    "5": "1.25rem",
    "6": "1.5rem",
    "8": "2rem",
    "10": "2.5rem",
    "12": "3rem",
    "16": "4rem",
    "20": "5rem",
}

SECTION_GAP: Final[str] = SPACING["8"]
CARD_GAP: Final[str] = SPACING["4"]
CONTROL_GAP: Final[str] = SPACING["3"]


def space(token: str | int) -> str:
    return SPACING.get(str(token), SPACING["4"])
