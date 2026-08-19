from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEMO_TENANT_PREFIX = "demo-"
DEMO_ORGANIZATION_ID = "de000000-0000-4000-8000-000000000020"
DEMO_ORGANIZATION_NAME = "Nexora Global Retail (Synthetic Demo)"
DEMO_DATA_PATH = Path(__file__).parents[1] / "data" / "demo" / "nexora_global_retail.json"


class DemoTenantError(RuntimeError):
    """Raised when synthetic data is requested outside the isolated demo boundary."""


def demo_mode_enabled() -> bool:
    return os.getenv("NEXORA_DEMO_MODE", "").strip().lower() in {"1", "true", "yes"}


def is_demo_tenant(organization_id: str) -> bool:
    normalized = str(organization_id or "").strip().lower()
    return normalized == DEMO_ORGANIZATION_ID or normalized.startswith(DEMO_TENANT_PREFIX)


def load_demo_tenant(organization_id: str) -> dict[str, Any]:
    """Load the immutable synthetic tenant without writing to production repositories."""
    if not demo_mode_enabled():
        raise DemoTenantError("NEXORA_DEMO_MODE is not enabled")
    if not is_demo_tenant(organization_id):
        raise DemoTenantError("synthetic data is restricted to the isolated demo tenant")

    payload = json.loads(DEMO_DATA_PATH.read_text(encoding="utf-8"))
    if payload.get("classification") != "SYNTHETIC_DEMONSTRATION_DATA":
        raise DemoTenantError("demo dataset classification is missing or invalid")
    if not str(payload.get("organization_id", "")).startswith(DEMO_TENANT_PREFIX):
        raise DemoTenantError("demo dataset tenant boundary is invalid")
    return payload
