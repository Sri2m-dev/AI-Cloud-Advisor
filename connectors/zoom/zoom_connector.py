"""Zoom connector placeholder for future SaaSOps telemetry."""

from __future__ import annotations

from connectors.common import BaseConnector


class ZoomConnector(BaseConnector):
    connector_name = "Zoom"
    status = "NOT_CONFIGURED"
    sync_frequency = "DAILY"
    sources = ["Users", "Licenses", "Activity"]
    tables_populated = ["technology_inventory", "license_cost"]

