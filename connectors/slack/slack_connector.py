"""Slack connector placeholder for future SaaSOps telemetry."""

from __future__ import annotations

from connectors.common import BaseConnector


class SlackConnector(BaseConnector):
    connector_name = "Slack"
    status = "NOT_CONFIGURED"
    sync_frequency = "DAILY"
    sources = ["Users", "Licenses", "Activity"]
    tables_populated = ["technology_inventory", "license_cost"]

