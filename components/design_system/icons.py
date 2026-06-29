from __future__ import annotations

from typing import Final


ICONS: Final[dict[str, str]] = {
    "home": "home",
    "executive": "bar-chart-3",
    "finance": "circle-dollar-sign",
    "cloud": "cloud",
    "technology": "network",
    "intelligence": "brain",
    "observability": "activity",
    "governance": "shield-check",
    "platform": "settings",
    "marketplace": "store",
    "administration": "users",
    "settings": "sliders-horizontal",
    "search": "search",
    "notifications": "bell",
    "profile": "user-circle",
    "success": "check-circle-2",
    "warning": "triangle-alert",
    "error": "circle-x",
    "info": "info",
    "trend_up": "trending-up",
    "trend_down": "trending-down",
    "ai": "sparkles",
    "cost": "banknote",
    "risk": "shield-alert",
    "approval": "badge-check",
}

NAVIGATION_SECTIONS: Final[list[dict[str, str]]] = [
    {"label": "Home", "icon": ICONS["home"]},
    {"label": "Executive", "icon": ICONS["executive"]},
    {"label": "Finance", "icon": ICONS["finance"]},
    {"label": "Cloud", "icon": ICONS["cloud"]},
    {"label": "Technology", "icon": ICONS["technology"]},
    {"label": "Intelligence", "icon": ICONS["intelligence"]},
    {"label": "Observability", "icon": ICONS["observability"]},
    {"label": "Governance", "icon": ICONS["governance"]},
    {"label": "Platform", "icon": ICONS["platform"]},
    {"label": "Marketplace", "icon": ICONS["marketplace"]},
    {"label": "Administration", "icon": ICONS["administration"]},
    {"label": "Settings", "icon": ICONS["settings"]},
]


def icon(name: str, fallback: str = "circle") -> str:
    return ICONS.get(name, fallback)
