"""GitHub Copilot connector adapter for AI license and usage syncs."""

from __future__ import annotations

from connectors.common import BaseConnector


class CopilotConnector(BaseConnector):
    connector_name = "GitHub Copilot"
    status = "CONNECTED"
    sync_frequency = "DAILY"
    sources = ["Licenses", "Users", "Usage"]
    tables_populated = ["technology_inventory", "license_cost", "recommendations"]

    def sync_licenses(self) -> dict:
        return self._sync_result("sync_licenses", 1, ["license_cost", "technology_inventory"], ["Licenses"])

    def sync_users(self) -> dict:
        return self._sync_result("sync_users", 2, ["technology_inventory"], ["Users"])

    def sync_usage(self) -> dict:
        return self._sync_result("sync_usage", 2, ["recommendations"], ["Usage"])

