from __future__ import annotations

from typing import Final


FONT_STACK: Final[str] = '"Inter", "Segoe UI", Arial, sans-serif'
MONO_STACK: Final[str] = '"JetBrains Mono", "SFMono-Regular", Consolas, monospace'

TYPOGRAPHY: Final[dict[str, dict[str, str]]] = {
    "display": {"font_size": "2.25rem", "line_height": "2.75rem", "font_weight": "700"},
    "h1": {"font_size": "1.875rem", "line_height": "2.375rem", "font_weight": "700"},
    "h2": {"font_size": "1.5rem", "line_height": "2rem", "font_weight": "650"},
    "h3": {"font_size": "1.25rem", "line_height": "1.75rem", "font_weight": "650"},
    "h4": {"font_size": "1.125rem", "line_height": "1.5rem", "font_weight": "600"},
    "h5": {"font_size": "1rem", "line_height": "1.375rem", "font_weight": "600"},
    "h6": {"font_size": "0.875rem", "line_height": "1.25rem", "font_weight": "600"},
    "body": {"font_size": "0.9375rem", "line_height": "1.5rem", "font_weight": "400"},
    "body_strong": {"font_size": "0.9375rem", "line_height": "1.5rem", "font_weight": "600"},
    "caption": {"font_size": "0.8125rem", "line_height": "1.125rem", "font_weight": "400"},
    "label": {"font_size": "0.8125rem", "line_height": "1rem", "font_weight": "600"},
    "code": {"font_size": "0.8125rem", "line_height": "1.25rem", "font_weight": "500"},
}


def type_style(name: str) -> dict[str, str]:
    return TYPOGRAPHY.get(name, TYPOGRAPHY["body"])
