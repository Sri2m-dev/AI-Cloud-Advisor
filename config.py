"""Centralized runtime configuration for AI-Cloud-Advisor."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    """Application settings loaded from environment variables."""

    app_title: str = os.getenv("APP_TITLE", "AI Cloud Advisor")
    default_username: str = os.getenv("APP_USERNAME", "admin")
    default_password: str = os.getenv("APP_PASSWORD", "cloud123")


CONFIG = AppConfig()

DEFAULT_ORG_ID = "bff29e99-1a33-4bf7-a2dc-3abe9bd2a03c"

