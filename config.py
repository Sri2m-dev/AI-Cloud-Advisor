"""Centralized runtime configuration for AI-Cloud-Advisor."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Application settings loaded from environment variables."""

    app_title: str = os.getenv("APP_TITLE", "Cloud Advisory Platform")
    default_username: str = os.getenv("APP_USERNAME", "admin")
    default_password: str = os.getenv("APP_PASSWORD", "cloud123")


CONFIG = AppConfig()
