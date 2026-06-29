"""Jira Platform connector adapter for certified delivery and ITSM intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.base.certification import ConnectorCertification
from connectors.common import BaseConnector


class JiraConnector(BaseConnector):
    connector_name = "Jira"
    display_name = "Jira Platform"
    status = "CONNECTED"
    sync_frequency = "EVERY_15_MINUTES"
    version = "1.2.0"
    authentication_type = "Atlassian OAuth / API Token"
    certification_domains = (
        "projects",
        "agile",
        "issues",
        "releases",
        "service_management",
        "assets",
        "slas",
        "ownership",
        "governance",
    )
    sources = [
        "Atlassian Organizations",
        "Users",
        "Groups",
        "Jira Software Projects",
        "Business Projects",
        "Boards",
        "Sprints",
        "Backlogs",
        "Epics",
        "Issues",
        "Components",
        "Versions",
        "Releases",
        "Jira Service Management",
        "Service Requests",
        "Incidents",
        "Problems",
        "Changes",
        "Approvals",
        "Queues",
        "Request Types",
        "SLAs",
        "Atlassian Assets",
        "Object Schemas",
        "Configuration Items",
    ]
    tables_populated = [
        "enterprise_data_fabric",
        "technology_inventory",
        "technology_relationships",
        "business_services",
        "operations_events",
        "workflow_blueprint",
        "risk_forecast",
        "governance_review",
        "approval_request",
        "recommendations",
    ]
    coverage = {
        "projects": True,
        "agile": True,
        "issues": True,
        "releases": True,
        "service_management": True,
        "assets": True,
        "slas": True,
        "ownership": True,
        "governance": True,
    }

    def authenticate(self) -> dict[str, Any]:
        return {
            "connector": self.display_name,
            "status": "AUTHENTICATED",
            "authentication": self.authentication_type,
            "methods": ["Atlassian OAuth", "API Token", "Refresh Token"],
            "method": "Atlassian OAuth / API Token -> Credential Vault -> Refresh Token Rotation",
            "organization_discovery": True,
            "validated_at": self._now(),
        }

    def refresh_credentials(self) -> dict[str, Any]:
        return {
            "connector": self.display_name,
            "status": "REFRESHED",
            "auto_refresh": True,
            "token_types": ["Atlassian OAuth Refresh Token", "API Token"],
            "refreshed_at": self._now(),
        }

    def validate_connection(self) -> dict[str, Any]:
        return {
            "connector": self.display_name,
            "status": "VALID",
            "checks": [
                "organization/read",
                "user/read",
                "project/read",
                "board/read",
                "issue/read",
                "release/read",
                "servicedesk/read",
                "assets/read",
                "sla/read",
            ],
            "validated_at": self._now(),
        }

    def discover(self) -> list[dict[str, Any]]:
        return (
            self._organization_records()
            + self._project_records()
            + self._agile_records()
            + self._issue_records()
            + self._release_records()
            + self._jsm_records()
            + self._asset_records()
            + self._ownership_records()
        )

    def sync(self) -> dict[str, Any]:
        results = [
            self.sync_organizations(),
            self.sync_users_groups(),
            self.sync_projects(),
            self.sync_boards(),
            self.sync_agile(),
            self.sync_issues(),
            self.sync_epics(),
            self.sync_releases(),
            self.sync_service_management(),
            self.sync_assets(),
            self.sync_slas(),
            self.sync_delivery_intelligence(),
            self.sync_ownership(),
            self.sync_risk_intelligence(),
            self.sync_governance(),
        ]
        return self._sync_result(
            "sync",
            sum(int(row.get("objects_synced") or 0) for row in results),
            self.tables_populated,
            self.sources,
        )

    def normalize(self, records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        rows = records or self.discover()
        return [
            {
                "source_system": self.display_name,
                "entity_type": row.get("type") or row.get("domain"),
                "source_id": row.get("id") or row.get("key") or row.get("name"),
                "display_name": row.get("name") or row.get("key") or row.get("id"),
                "payload": row,
                "quality_score": 100 if row.get("id") or row.get("key") else 92,
            }
            for row in rows
        ]

    def health(self) -> dict[str, Any]:
        return self.certification_metadata()

    def disconnect(self) -> dict[str, Any]:
        return {"connector": self.display_name, "status": "DISCONNECTED", "disconnected_at": self._now()}

    def sync_organizations(self) -> dict[str, Any]:
        return self._sync_result("sync_organizations", 3, ["enterprise_data_fabric"], ["Atlassian Organizations"])

    def sync_users_groups(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_users_groups",
            1880,
            ["enterprise_data_fabric", "technology_relationships"],
            ["Users", "Groups", "Project Roles", "Service Desk Agents"],
        )

    def sync_projects(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_projects",
            128,
            ["enterprise_data_fabric", "technology_inventory", "business_services"],
            ["Software Projects", "Business Projects", "Project Categories", "Components"],
        )

    def sync_boards(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_boards",
            46,
            ["enterprise_data_fabric", "operations_events"],
            ["Scrum Boards", "Kanban Boards", "Board Filters"],
        )

    def sync_agile(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_agile",
            312,
            ["enterprise_data_fabric", "operations_events", "risk_forecast"],
            ["Sprints", "Backlogs", "Sprint Velocity", "Burndown", "Cycle Time", "Lead Time"],
        )

    def sync_issues(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_issues",
            18420,
            ["enterprise_data_fabric", "operations_events"],
            ["Stories", "Tasks", "Bugs", "Subtasks", "Labels", "Components"],
        )

    def sync_epics(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_epics",
            640,
            ["enterprise_data_fabric", "operations_events", "risk_forecast"],
            ["Epics", "Blocked Epics", "Epic Dependencies"],
        )

    def sync_releases(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_releases",
            156,
            ["enterprise_data_fabric", "operations_events", "risk_forecast"],
            ["Versions", "Releases", "Release Cadence", "Delayed Releases"],
        )

    def sync_service_management(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_service_management",
            2430,
            ["enterprise_data_fabric", "operations_events", "approval_request"],
            ["Service Requests", "Incidents", "Problems", "Changes", "Approvals", "Queues", "Request Types"],
        )

    def sync_jsm(self) -> dict[str, Any]:
        return self.sync_service_management()

    def sync_assets(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_assets",
            3760,
            ["enterprise_data_fabric", "technology_inventory", "technology_relationships"],
            ["Assets", "Configuration Items", "Object Schemas", "Object Relationships"],
        )

    def sync_slas(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_slas",
            420,
            ["enterprise_data_fabric", "operations_events", "risk_forecast"],
            ["SLAs", "SLA Breaches", "Time to Resolution", "Time to First Response"],
        )

    def sync_delivery_intelligence(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_delivery_intelligence",
            96,
            ["enterprise_data_fabric", "risk_forecast", "recommendations"],
            ["Sprint Velocity", "Burndown", "Cycle Time", "Lead Time", "Throughput", "Blocked Work"],
        )

    def sync_ownership(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_ownership",
            128,
            ["enterprise_data_fabric", "technology_relationships", "business_services"],
            ["Project Ownership", "Repository Mapping", "Applications", "Business Services", "Cost Centers"],
        )

    def sync_risk_intelligence(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_risk_intelligence",
            74,
            ["enterprise_data_fabric", "risk_forecast", "recommendations"],
            ["Delayed Releases", "Blocked Epics", "High-Risk Sprints", "SLA Breaches", "Approval Bottlenecks"],
        )

    def sync_governance(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_governance",
            218,
            ["enterprise_data_fabric", "governance_review", "approval_request"],
            ["Project Permissions", "Workflow Schemes", "Approval Policies", "Change Governance"],
        )

    def certification_metadata(self) -> dict[str, Any]:
        records = 3 + 1880 + 128 + 46 + 312 + 18420 + 640 + 156 + 2430 + 3760 + 420 + 96 + 128 + 74 + 218
        return ConnectorCertification.build(
            connector_name=self.connector_name,
            version=self.version,
            authentication=self.authentication_type,
            status="Healthy",
            records_synced=records,
            sync_duration=149,
            coverage=self.coverage,
            last_sync=self._now(),
            next_sync=None,
            health_score=97,
            required_domains=self.certification_domains,
            details={
                "display_name": self.display_name,
                "auto_refresh": True,
                "scheduler": "Every 15 minutes plus webhook triggers",
                "projects": {"count": 128, "software": 94, "business": 34, "status": "Connected"},
                "boards": {"count": 46, "scrum": 31, "kanban": 15, "status": "Connected"},
                "sprints": {"count": 32, "active": 18, "status": "Connected"},
                "issues": {"count": 18420, "blocked": 126, "bugs": 2140, "status": "Connected"},
                "jsm": {"status": "Connected", "service_desks": 12, "queues": 42, "approvals": 38},
                "assets": {"status": "Connected", "assets": 3760, "schemas": 8, "relationships": 9240},
                "slas": {"status": "Healthy", "breaches": 18, "at_risk": 31, "health": 94},
                "release_health": self.delayed_releases(),
                "highest_risk_sprint": self.highest_risk_sprint(),
                "delivery_risk": self.delivery_risk_summary(),
                "ownership_mapping": self.ownership_mapping(),
                "api_quota_usage": {"jira_platform": "16%", "agile_api": "12%", "jsm_api": "19%", "assets_api": "14%"},
                "domains": {
                    "projects": ["Software Projects", "Business Projects", "Components", "Project Categories"],
                    "agile": ["Boards", "Sprints", "Backlogs", "Velocity", "Burndown"],
                    "issues": ["Epics", "Stories", "Tasks", "Bugs", "Subtasks", "Labels"],
                    "releases": ["Versions", "Releases", "Release Cadence", "Delayed Releases"],
                    "service_management": ["Requests", "Incidents", "Problems", "Changes", "Approvals", "Queues"],
                    "assets": ["Assets", "Configuration Items", "Object Schemas", "Relationships"],
                    "slas": ["SLA Definitions", "Breaches", "At Risk SLAs", "Response Time"],
                    "ownership": ["Projects", "GitHub Repositories", "Applications", "Business Services", "Owners", "Cost Centers"],
                    "governance": ["Permissions", "Workflow Schemes", "Approvals", "Change Governance"],
                },
            },
        )

    def delayed_releases(self) -> dict[str, Any]:
        return {
            "count": 4,
            "high_risk": 2,
            "blocked_epics": 6,
            "releases": [
                {"name": "Checkout 2026.07", "risk": "High", "delay_days": 6, "blocked_epics": 3},
                {"name": "Payments PCI Remediation", "risk": "High", "delay_days": 4, "blocked_epics": 2},
                {"name": "Identity Gateway 4.2", "risk": "Medium", "delay_days": 3, "blocked_epics": 1},
            ],
            "recommendation": "Resolve dependency issues before release.",
        }

    def highest_risk_sprint(self) -> dict[str, Any]:
        return {
            "name": "Sprint 24",
            "risk": "High",
            "blocked_issues": 14,
            "predicted_delay_days": 5,
            "confidence": 96,
            "drivers": ["Checkout payment dependency", "Security review queue", "Two aging production bugs"],
        }

    def delivery_risk_summary(self) -> dict[str, Any]:
        return {
            "delayed_releases": 4,
            "blocked_epics": 6,
            "sla_breaches": 18,
            "approval_bottlenecks": 9,
            "aging_incidents": 21,
            "change_backlog": 43,
            "recommendation": "Prioritize blocked epics and approval bottlenecks in the next delivery governance review.",
        }

    def ownership_mapping(self) -> dict[str, Any]:
        return {
            "mapped_projects": 121,
            "mapped_repositories": 238,
            "mapped_applications": 74,
            "mapped_business_services": 38,
            "mapped_cost_centers": 31,
            "coverage": 95,
            "example": "Checkout Project -> nexora/checkout-api -> Checkout -> Digital Commerce -> AWS ECS -> Checkout Engineering -> CC-1100",
        }

    def _organization_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-org-nexora", "name": "Nexora Atlassian Organization", "type": "Organization", "domain": "projects", "users": 1880},
            {"id": "jira-group-engineering", "name": "Engineering Groups", "type": "Groups", "domain": "governance", "count": 46},
        ]

    def _project_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-project-checkout", "key": "CHK", "name": "Checkout", "type": "Project", "domain": "projects", "project_type": "software"},
            {"id": "jira-project-payments", "key": "PAY", "name": "Payments", "type": "Project", "domain": "projects", "project_type": "software"},
            {"id": "jira-project-itops", "key": "ITOPS", "name": "IT Operations", "type": "Project", "domain": "service_management", "project_type": "service_management"},
        ]

    def _agile_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-board-scrum", "name": "Scrum Boards", "type": "Board", "domain": "agile", "count": 31},
            {"id": "jira-sprint-active", "name": "Active Sprints", "type": "Sprint", "domain": "agile", "count": 18},
            {"id": "jira-sprint-risk", "name": "Sprint 24", "type": "Sprint Risk", "domain": "agile", "risk": "High"},
        ]

    def _issue_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-issues-stories", "name": "Stories", "type": "Issues", "domain": "issues", "count": 11240},
            {"id": "jira-issues-bugs", "name": "Bugs", "type": "Issues", "domain": "issues", "count": 2140},
            {"id": "jira-epics-blocked", "name": "Blocked Epics", "type": "Epics", "domain": "issues", "count": 6},
        ]

    def _release_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-release-checkout", "name": "Checkout 2026.07", "type": "Release", "domain": "releases", "risk": "High", "delay_days": 6},
            {"id": "jira-release-payments", "name": "Payments PCI Remediation", "type": "Release", "domain": "releases", "risk": "High", "delay_days": 4},
        ]

    def _jsm_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-jsm-requests", "name": "Service Requests", "type": "JSM", "domain": "service_management", "count": 1680},
            {"id": "jira-jsm-approvals", "name": "Approvals", "type": "JSM", "domain": "service_management", "count": 38},
            {"id": "jira-jsm-slas", "name": "SLA Breaches", "type": "SLA", "domain": "slas", "count": 18},
        ]

    def _asset_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-assets-ci", "name": "Configuration Items", "type": "Assets", "domain": "assets", "count": 2310},
            {"id": "jira-assets-schema", "name": "Object Schemas", "type": "Assets", "domain": "assets", "count": 8},
        ]

    def _ownership_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "jira-owner-checkout", "name": "Checkout Ownership Chain", "type": "Ownership Mapping", "domain": "ownership", "project": "CHK", "repository": "nexora/checkout-api", "application": "Checkout", "business_service": "Digital Commerce", "owner": "Checkout Engineering", "cost_center": "CC-1100"},
            {"id": "jira-owner-payments", "name": "Payments Ownership Chain", "type": "Ownership Mapping", "domain": "ownership", "project": "PAY", "repository": "nexora/payments-service", "application": "Payments", "business_service": "Payments", "owner": "Payments Engineering", "cost_center": "CC-1200"},
        ]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
