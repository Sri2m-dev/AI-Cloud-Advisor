from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from components.design_system.animations import TRANSITIONS
from components.design_system.borders import RADIUS
from components.design_system.colors import COLORS, STATUS_COLORS, palette
from components.design_system.shadows import SHADOWS
from components.design_system.spacing import SPACING
from components.design_system.typography import FONT_STACK, MONO_STACK, TYPOGRAPHY


@dataclass(frozen=True)
class NexoraTheme:
    mode: str
    colors: dict[str, str]
    typography: dict[str, dict[str, str]]
    spacing: dict[str, str]
    radius: dict[str, str]
    shadows: dict[str, str]
    status_colors: dict[str, str]

    def token_map(self) -> dict[str, str]:
        tokens = {
            "--nexora-font": FONT_STACK,
            "--nexora-mono": MONO_STACK,
            "--nexora-background": self.colors["background"],
            "--nexora-surface": self.colors["surface"],
            "--nexora-surface-alt": self.colors["surface_alt"],
            "--nexora-text": self.colors["text"],
            "--nexora-text-muted": self.colors["text_muted"],
            "--nexora-border": self.colors["border"],
            "--nexora-border-strong": self.colors["neutral"],
            "--nexora-primary": self.colors["primary"],
            "--nexora-primary-hover": self.colors["primary_hover"],
            "--nexora-secondary": self.colors["secondary"],
            "--nexora-success": self.colors["success"],
            "--nexora-warning": self.colors["warning"],
            "--nexora-error": self.colors["error"],
            "--nexora-info": self.colors["info"],
            "--nexora-radius-card": self.radius["lg"],
            "--nexora-radius-control": self.radius["md"],
            "--nexora-shadow-card": self.shadows["sm"],
            "--nexora-transition-button": TRANSITIONS["button"],
        }
        for key, value in self.spacing.items():
            tokens[f"--nexora-space-{key}"] = value
        return tokens

    def css(self) -> str:
        variables = ";\n".join(f"{key}: {value}" for key, value in self.token_map().items())
        body = self.typography["body"]
        caption = self.typography["caption"]
        return f"""
<style>
:root {{
{variables};
}}
.stApp {{
    background: var(--nexora-background);
    color: var(--nexora-text);
    font-family: var(--nexora-font);
}}
.nexora-page-shell {{
    max-width: 1440px;
    margin: 0 auto;
    padding: var(--nexora-space-4) var(--nexora-space-6) var(--nexora-space-8);
}}
.nexora-card {{
    background: var(--nexora-surface);
    border: 1px solid var(--nexora-border);
    border-radius: var(--nexora-radius-card);
    box-shadow: var(--nexora-shadow-card);
    padding: var(--nexora-space-4);
}}
.nexora-caption {{
    color: var(--nexora-text-muted);
    font-size: {caption["font_size"]};
    line-height: {caption["line_height"]};
}}
.nexora-body {{
    font-size: {body["font_size"]};
    line-height: {body["line_height"]};
}}
button[kind="primary"] {{
    border-radius: var(--nexora-radius-control);
    transition: var(--nexora-transition-button);
}}
</style>
"""


def get_theme(mode: str = "light") -> NexoraTheme:
    selected = mode if mode in COLORS else "light"
    return NexoraTheme(
        mode=selected,
        colors=palette(selected),
        typography=TYPOGRAPHY,
        spacing=SPACING,
        radius=RADIUS,
        shadows=SHADOWS,
        status_colors=STATUS_COLORS,
    )


def inject_theme(mode: str = "light") -> NexoraTheme:
    theme = get_theme(mode)
    st.markdown(theme.css(), unsafe_allow_html=True)
    return theme


def theme_tokens(mode: str = "light") -> dict[str, Any]:
    theme = get_theme(mode)
    return {
        "mode": theme.mode,
        "colors": theme.colors,
        "typography": theme.typography,
        "spacing": theme.spacing,
        "radius": theme.radius,
        "shadows": theme.shadows,
        "status_colors": theme.status_colors,
    }
