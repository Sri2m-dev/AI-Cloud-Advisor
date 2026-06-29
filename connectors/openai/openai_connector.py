"""OpenAI connector adapter for AI governance usage, spend, model, and user syncs."""

from __future__ import annotations

from connectors.common import BaseConnector


class OpenAIConnector(BaseConnector):
    connector_name = "OpenAI"
    status = "CONNECTED"
    sync_frequency = "DAILY"
    sources = ["Users", "Spend", "Models", "Usage"]
    tables_populated = ["technology_inventory", "license_cost", "recommendations"]

    def sync_users(self) -> dict:
        return self._sync_result("sync_users", 2, ["technology_inventory"], ["Users"])

    def sync_spend(self) -> dict:
        return self._sync_result("sync_spend", 1, ["license_cost"], ["Spend", "Usage"])

    def sync_models(self) -> dict:
        return self._sync_result("sync_models", 3, ["technology_inventory"], ["Models", "Usage"])

    def sync_usage(self) -> dict:
        return self._sync_result("sync_usage", 3, ["technology_inventory", "recommendations"], ["Usage"])

