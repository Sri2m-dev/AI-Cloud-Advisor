from __future__ import annotations

from typing import Any


def resources_to_technology_inventory(
    resources: list[dict[str, Any]],
    vendor_name: str,
    cloud_provider: str,
    source_system: str,
    default_owner_department: str = "CloudOps",
    default_business_owner: str = "CloudOps Lead",
    default_technical_owner: str = "Cloud Architect",
) -> list[dict[str, Any]]:
    rows = []
    for resource in resources:
        technology_name = resource.get("technology_name") or resource.get("asset_name") or resource.get("asset_id")
        if not technology_name:
            continue
        rows.append(
            {
                "technology_name": technology_name,
                "technology_type": resource.get("technology_type", "Cloud Resource"),
                "vendor_name": resource.get("vendor_name", vendor_name),
                "category": resource.get("category", resource.get("asset_type", "Cloud Resource")),
                "cloud_provider": resource.get("cloud_provider", cloud_provider),
                "owner_department": resource.get("owner_department", default_owner_department),
                "business_owner": resource.get("business_owner", default_business_owner),
                "technical_owner": resource.get("technical_owner", default_technical_owner),
                "annual_cost": resource.get("annual_cost", 0),
                "status": resource.get("status", "ACTIVE"),
                "source_system": source_system,
            }
        )
    return rows


def resources_to_discovered_assets(
    resources: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    connector_name: str,
    provider: str,
    source_system: str,
    last_seen_at: str,
) -> list[dict[str, Any]]:
    account_id = str(accounts[0].get("account_id", "")) if accounts else ""
    assets = []
    for resource in resources:
        asset_id = str(resource.get("asset_id") or resource.get("resource_id") or resource.get("technology_name") or "")
        if not asset_id:
            continue
        assets.append(
            {
                "connector_name": connector_name,
                "provider": provider,
                "asset_type": resource.get("category", resource.get("asset_type", "Cloud Resource")),
                "asset_id": asset_id,
                "asset_name": resource.get("asset_name") or resource.get("technology_name") or asset_id,
                "region": resource.get("region", ""),
                "account_id": account_id,
                "status": resource.get("status", ""),
                "source_system": source_system,
                "raw_payload": resource,
                "last_seen_at": last_seen_at,
            }
        )
    return assets


def resources_to_relationships(
    resources: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    provider: str,
    platform_name: str,
) -> list[dict[str, Any]]:
    relationships = []
    account_name = platform_name
    account_id = ""
    if accounts:
        account_id = str(accounts[0].get("account_id", ""))
        account_name = accounts[0].get("account_name") or f"{platform_name} Account {account_id}"
    for resource in resources:
        resource_name = resource.get("technology_name") or resource.get("asset_name") or resource.get("asset_id")
        if not resource_name:
            continue
        category = resource.get("category") or resource.get("asset_type") or "Cloud Resource"
        relationships.extend(
            [
                {
                    "source_type": "Cloud Account",
                    "source_name": account_name,
                    "relationship_type": "HAS_RESOURCE",
                    "target_type": category,
                    "target_name": resource_name,
                },
                {
                    "source_type": category,
                    "source_name": resource_name,
                    "relationship_type": "BELONGS_TO",
                    "target_type": "Cloud Platform",
                    "target_name": provider,
                },
                {
                    "source_type": category,
                    "source_name": resource_name,
                    "relationship_type": "COST_SOURCE_FOR",
                    "target_type": "Cost Domain",
                    "target_name": "Cloud Spend",
                },
            ]
        )
    return relationships

