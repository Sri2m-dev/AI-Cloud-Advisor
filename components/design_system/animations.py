from __future__ import annotations

from typing import Final


ANIMATIONS: Final[dict[str, str]] = {
    "duration_fast": "120ms",
    "duration_base": "180ms",
    "duration_slow": "260ms",
    "ease_standard": "cubic-bezier(0.2, 0, 0, 1)",
    "ease_emphasized": "cubic-bezier(0.2, 0, 0, 1.2)",
}

TRANSITIONS: Final[dict[str, str]] = {
    "button": "background-color 180ms cubic-bezier(0.2, 0, 0, 1), border-color 180ms cubic-bezier(0.2, 0, 0, 1)",
    "card": "box-shadow 180ms cubic-bezier(0.2, 0, 0, 1), transform 180ms cubic-bezier(0.2, 0, 0, 1)",
    "nav": "color 120ms cubic-bezier(0.2, 0, 0, 1), background-color 120ms cubic-bezier(0.2, 0, 0, 1)",
}
