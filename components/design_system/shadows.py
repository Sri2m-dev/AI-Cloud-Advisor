from __future__ import annotations

from typing import Final


SHADOWS: Final[dict[str, str]] = {
    "none": "none",
    "xs": "0 1px 2px rgba(15, 23, 42, 0.06)",
    "sm": "0 2px 6px rgba(15, 23, 42, 0.08)",
    "md": "0 8px 20px rgba(15, 23, 42, 0.10)",
    "lg": "0 18px 40px rgba(15, 23, 42, 0.14)",
    "focus": "0 0 0 3px rgba(31, 111, 235, 0.22)",
}

ELEVATION: Final[dict[str, dict[str, str]]] = {
    "flat": {"box_shadow": SHADOWS["none"], "z_index": "0"},
    "raised": {"box_shadow": SHADOWS["sm"], "z_index": "1"},
    "overlay": {"box_shadow": SHADOWS["md"], "z_index": "10"},
    "modal": {"box_shadow": SHADOWS["lg"], "z_index": "100"},
}


def shadow(token: str = "sm") -> str:
    return SHADOWS.get(token, SHADOWS["sm"])
