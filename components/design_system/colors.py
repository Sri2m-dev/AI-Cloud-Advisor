from __future__ import annotations

from typing import Final


COLORS: Final[dict[str, dict[str, str]]] = {
    "light": {
        "background": "#f7f9fc",
        "surface": "#ffffff",
        "surface_alt": "#eef3f8",
        "text": "#172033",
        "text_muted": "#5d6b82",
        "border": "#d9e2ec",
        "primary": "#1f6feb",
        "primary_hover": "#1557c0",
        "secondary": "#14b8a6",
        "accent": "#f59e0b",
        "success": "#16a34a",
        "warning": "#d97706",
        "error": "#dc2626",
        "info": "#0284c7",
        "neutral": "#64748b",
    },
    "dark": {
        "background": "#0f172a",
        "surface": "#172033",
        "surface_alt": "#1e293b",
        "text": "#f8fafc",
        "text_muted": "#b6c2d2",
        "border": "#334155",
        "primary": "#60a5fa",
        "primary_hover": "#93c5fd",
        "secondary": "#2dd4bf",
        "accent": "#fbbf24",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#f87171",
        "info": "#38bdf8",
        "neutral": "#94a3b8",
    },
}

STATUS_COLORS: Final[dict[str, str]] = {
    "healthy": "#16a34a",
    "ready": "#16a34a",
    "passed": "#16a34a",
    "warning": "#d97706",
    "watch": "#d97706",
    "critical": "#dc2626",
    "failed": "#dc2626",
    "blocked": "#b91c1c",
    "unknown": "#64748b",
    "info": "#0284c7",
}

CHART_COLORS: Final[list[str]] = [
    "#1f6feb",
    "#14b8a6",
    "#f59e0b",
    "#7c3aed",
    "#dc2626",
    "#0891b2",
    "#65a30d",
    "#475569",
]


def palette(mode: str = "light") -> dict[str, str]:
    return COLORS.get(mode, COLORS["light"])


def status_color(status: str | None) -> str:
    key = str(status or "unknown").strip().lower()
    return STATUS_COLORS.get(key, STATUS_COLORS["unknown"])
