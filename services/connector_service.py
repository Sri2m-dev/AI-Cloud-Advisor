from __future__ import annotations

from typing import Any

import pandas as pd

from connectors.connector_registry import get_connector_registry


DEMO_CONNECTOR_HEALTH = {
    "AWS": {"Status": "Connected", "Last Sync": "5 min ago", "Assets": 1245},
    "Azure": {"Status": "Connected", "Last Sync": "10 min ago", "Assets": 456},
    "GitHub": {"Status": "Connected", "Last Sync": "1 hour ago", "Assets": 180},
    "Microsoft 365": {"Status": "Connected", "Last Sync": "15 min ago", "Assets": 890},
}


class ConnectorService:
    @staticmethod
    def get_connector_rows() -> list[dict[str, Any]]:
        registry = {row["connector_name"]: row for row in get_connector_registry()}
        rows = []
        for connector_name, demo in DEMO_CONNECTOR_HEALTH.items():
            registry_row = registry.get(connector_name, {})
            rows.append(
                {
                    "Connector": "M365" if connector_name == "Microsoft 365" else connector_name,
                    "Status": demo["Status"],
                    "Last Sync": demo["Last Sync"],
                    "Assets": demo["Assets"],
                    "Sync Frequency": registry_row.get("sync_frequency", "DAILY"),
                    "Tables": ", ".join(registry_row.get("tables_populated", [])),
                }
            )
        return rows

    @staticmethod
    def get_connector_kpis() -> dict[str, Any]:
        rows = ConnectorService.get_connector_rows()
        connected = sum(1 for row in rows if row["Status"].lower() == "connected")
        assets = sum(int(row["Assets"] or 0) for row in rows)
        return {
            "Connected Connectors": connected,
            "Assets Synced": assets,
            "Daily Syncs": sum(1 for row in rows if row["Sync Frequency"] == "DAILY"),
            "Product Readiness": "High",
        }

    @staticmethod
    def connector_dataframe() -> pd.DataFrame:
        rows = ConnectorService.get_connector_rows()
        return pd.DataFrame(rows, columns=["Connector", "Status", "Last Sync", "Assets", "Sync Frequency", "Tables"])

    @staticmethod
    def get_enablement_flow() -> list[dict[str, str]]:
        return [
            {"Step": "Connect AWS", "Target": "Cloud spend, accounts, resources, recommendations", "Outcome": "Technology Portfolio, TBM, Digital Twin"},
            {"Step": "Connect Azure", "Target": "Cloud spend, resources, Advisor recommendations", "Outcome": "Technology Portfolio, FinOps, Copilot"},
            {"Step": "Connect Microsoft 365", "Target": "Users, licenses, inactive users, groups", "Outcome": "SaaS Intelligence, AI Governance, Chargeback"},
            {"Step": "15-minute sync", "Target": "Normalize source data into Nexora tables", "Outcome": "Portfolio, AI, TBM, Digital Twin, Copilot populated"},
        ]

    @staticmethod
    def get_executive_narrative() -> str:
        kpis = ConnectorService.get_connector_kpis()
        return (
            f"Nexora currently has {kpis['Connected Connectors']} primary data-source connectors active, "
            f"with {kpis['Assets Synced']:,} assets synchronized across cloud, SaaS, engineering, and identity systems. "
            "This connector layer is the foundation for automatically populating the Technology Portfolio, "
            "Application Portfolio, SaaS Intelligence, AI Governance, TBM, Digital Twin, and Copilot experiences "
            "without manual data entry."
        )

