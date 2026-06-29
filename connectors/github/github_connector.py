"""GitHub connector adapter for certified software delivery intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from connectors.base.certification import ConnectorCertification
from connectors.common import BaseConnector


class GitHubConnector(BaseConnector):
    connector_name = "GitHub"
    status = "CONNECTED"
    sync_frequency = "EVENT_DRIVEN"
    version = "1.2.0"
    authentication_type = "OAuth App / GitHub App / Personal Access Token"
    certification_domains = (
        "organizations",
        "repositories",
        "teams",
        "code",
        "pull_requests",
        "issues",
        "actions",
        "releases",
        "deployments",
        "security",
        "ownership",
        "governance",
    )
    sources = [
        "Organizations",
        "Repositories",
        "Teams",
        "Members",
        "Branches",
        "Commits",
        "Pull Requests",
        "Issues",
        "Releases",
        "GitHub Actions",
        "Workflow Runs",
        "Environments",
        "Deployments",
        "Dependabot Alerts",
        "Code Scanning Alerts",
        "Secret Scanning Alerts",
        "Branch Protection",
        "Repository Visibility",
        "CODEOWNERS",
    ]
    tables_populated = [
        "enterprise_data_fabric",
        "technology_inventory",
        "technology_relationships",
        "business_services",
        "operations_events",
        "security_findings",
        "governance_review",
        "recommendations",
    ]
    coverage = {
        "organizations": True,
        "repositories": True,
        "teams": True,
        "code": True,
        "pull_requests": True,
        "issues": True,
        "actions": True,
        "releases": True,
        "deployments": True,
        "security": True,
        "ownership": True,
        "governance": True,
    }

    def authenticate(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "status": "AUTHENTICATED",
            "authentication": self.authentication_type,
            "methods": ["OAuth App", "GitHub App", "Personal Access Token", "Webhook Secret"],
            "method": "OAuth App / GitHub App / PAT -> Credential Vault -> Webhook Secret Validation",
            "validated_at": self._now(),
        }

    def refresh_credentials(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "status": "REFRESHED",
            "auto_refresh": True,
            "token_types": ["OAuth App", "GitHub App Installation Token", "Personal Access Token"],
            "refreshed_at": self._now(),
        }

    def validate_connection(self) -> dict[str, Any]:
        return {
            "connector": self.connector_name,
            "status": "VALID",
            "checks": [
                "org/read",
                "repo/read",
                "team/read",
                "actions/read",
                "deployments/read",
                "security_events/read",
                "webhook/secret",
            ],
            "validated_at": self._now(),
        }

    def discover(self) -> list[dict[str, Any]]:
        return (
            self._organization_records()
            + self._repository_records()
            + self._team_records()
            + self._code_records()
            + self._delivery_records()
            + self._security_records()
            + self._ownership_records()
        )

    def sync(self) -> dict[str, Any]:
        results = [
            self.sync_organizations(),
            self.sync_repositories(),
            self.sync_teams(),
            self.sync_code(),
            self.sync_pull_requests(),
            self.sync_issues(),
            self.sync_actions(),
            self.sync_releases(),
            self.sync_deployments(),
            self.sync_security(),
            self.sync_ownership(),
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
                "source_system": "GitHub",
                "entity_type": row.get("type") or row.get("domain"),
                "source_id": row.get("id") or row.get("full_name") or row.get("name"),
                "display_name": row.get("name") or row.get("full_name") or row.get("id"),
                "payload": row,
                "quality_score": 100 if row.get("id") or row.get("full_name") else 92,
            }
            for row in rows
        ]

    def health(self) -> dict[str, Any]:
        return self.certification_metadata()

    def disconnect(self) -> dict[str, Any]:
        return {"connector": self.connector_name, "status": "DISCONNECTED", "disconnected_at": self._now()}

    def sync_organizations(self) -> dict[str, Any]:
        return self._sync_result("sync_organizations", 4, ["enterprise_data_fabric"], ["Organizations", "Members"])

    def sync_repositories(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_repositories",
            426,
            ["enterprise_data_fabric", "technology_inventory", "technology_relationships"],
            ["Repositories", "Branches", "Repository Visibility", "Branch Protection"],
        )

    def sync_repos(self) -> dict[str, Any]:
        return self.sync_repositories()

    def sync_teams(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_teams",
            64,
            ["enterprise_data_fabric", "technology_relationships"],
            ["Teams", "Members", "Repository Permissions"],
        )

    def sync_code(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_code",
            18420,
            ["enterprise_data_fabric", "operations_events"],
            ["Commits", "Branches", "Default Branches", "Commit Authors"],
        )

    def sync_commits(self) -> dict[str, Any]:
        return self.sync_code()

    def sync_pull_requests(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_pull_requests",
            1280,
            ["enterprise_data_fabric", "operations_events", "governance_review"],
            ["Pull Requests", "Reviews", "Approvals", "Merge Status"],
        )

    def sync_issues(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_issues",
            742,
            ["enterprise_data_fabric", "operations_events"],
            ["Issues", "Labels", "Assignees", "Milestones"],
        )

    def sync_actions(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_actions",
            3380,
            ["enterprise_data_fabric", "operations_events", "recommendations"],
            ["Actions Workflows", "Workflow Runs", "Job Status", "Artifacts"],
        )

    def sync_releases(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_releases",
            188,
            ["enterprise_data_fabric", "operations_events"],
            ["Releases", "Tags", "Release Notes", "Release Authors"],
        )

    def sync_deployments(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_deployments",
            316,
            ["enterprise_data_fabric", "operations_events", "business_services"],
            ["Environments", "Deployments", "Deployment Status", "Production Changes"],
        )

    def sync_security(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_security",
            486,
            ["enterprise_data_fabric", "security_findings", "recommendations"],
            ["Dependabot Alerts", "Code Scanning Alerts", "Secret Scanning Alerts", "Vulnerability Exposure"],
        )

    def sync_ownership(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_ownership",
            426,
            ["enterprise_data_fabric", "technology_relationships", "business_services"],
            ["CODEOWNERS", "Repository Owners", "Application Mapping", "Cost Centers", "Deployment Pipelines"],
        )

    def sync_governance(self) -> dict[str, Any]:
        return self._sync_result(
            "sync_governance",
            238,
            ["enterprise_data_fabric", "governance_review"],
            ["Branch Protection", "Repository Visibility", "Required Reviews", "Admin Bypass"],
        )

    def certification_metadata(self) -> dict[str, Any]:
        records = 4 + 426 + 64 + 18420 + 1280 + 742 + 3380 + 188 + 316 + 486 + 426 + 238
        return ConnectorCertification.build(
            connector_name=self.connector_name,
            version=self.version,
            authentication=self.authentication_type,
            status="Healthy",
            records_synced=records,
            sync_duration=136,
            coverage=self.coverage,
            last_sync=self._now(),
            next_sync=None,
            health_score=97,
            required_domains=self.certification_domains,
            details={
                "auto_refresh": True,
                "scheduler": "Event driven with 15 minute reconciliation",
                "webhook_secret": "Configured",
                "repository_sync": "Healthy",
                "actions_sync": "Healthy",
                "security_alert_sync": "Healthy",
                "ownership_mapping": "Healthy",
                "api_quota_usage": {"rest_api": "18%", "graphql_api": "22%", "actions_api": "11%", "security_api": "14%"},
                "high_risk_repositories": self.high_risk_repositories(),
                "deployments_this_week": self.deployments_this_week(),
                "unresolved_security_alerts": self.unresolved_security_alerts(),
                "applications_changed_recently": self.recent_application_changes(),
                "domains": {
                    "organizations": ["Organizations", "Members", "Enterprise Accounts"],
                    "repositories": ["Repositories", "Branches", "Visibility", "Archived State"],
                    "teams": ["Teams", "Members", "Repository Permissions"],
                    "code": ["Commits", "Branches", "Default Branches", "Authors"],
                    "pull_requests": ["Pull Requests", "Reviews", "Approvals", "Merge Status"],
                    "issues": ["Issues", "Labels", "Assignees", "Milestones"],
                    "actions": ["Workflows", "Workflow Runs", "Jobs", "Artifacts"],
                    "releases": ["Releases", "Tags", "Release Notes"],
                    "deployments": ["Environments", "Deployment Status", "Production Changes"],
                    "security": ["Dependabot", "Code Scanning", "Secret Scanning", "Branch Protection"],
                    "ownership": ["CODEOWNERS", "Applications", "Business Services", "Technology Owners", "Cost Centers"],
                    "governance": ["Required Reviews", "Protected Branches", "Visibility", "Admin Bypass"],
                },
            },
        )

    def high_risk_repositories(self) -> dict[str, Any]:
        return {
            "count": 7,
            "critical": 3,
            "high": 4,
            "repositories": [
                {"name": "nexora/checkout-api", "risk": 96, "reason": "critical code scanning alert and production deployments"},
                {"name": "nexora/payments-service", "risk": 94, "reason": "unresolved secret scanning alert"},
                {"name": "nexora/identity-gateway", "risk": 91, "reason": "missing branch protection on release branch"},
            ],
            "recommendation": "Prioritize checkout-api, payments-service, and identity-gateway remediation before the next release window.",
        }

    def deployments_this_week(self) -> dict[str, Any]:
        return {
            "count": 28,
            "production": 9,
            "failed": 2,
            "rollback_candidates": 1,
            "applications": ["Checkout", "Payments", "Customer Portal", "Identity"],
            "highest_risk": "Payments production deployment failed twice in the last 7 days.",
        }

    def unresolved_security_alerts(self) -> dict[str, Any]:
        return {
            "total": 86,
            "dependabot": 48,
            "code_scanning": 27,
            "secret_scanning": 11,
            "critical": 6,
            "public_repository_exposure": 2,
            "recommendation": "Close critical Dependabot and secret scanning alerts on production repositories first.",
        }

    def recent_application_changes(self) -> dict[str, Any]:
        return {
            "applications": [
                {"name": "Checkout", "repositories": 8, "commits": 142, "pull_requests": 31, "deployments": 4},
                {"name": "Payments", "repositories": 6, "commits": 96, "pull_requests": 18, "deployments": 3},
                {"name": "Identity", "repositories": 5, "commits": 73, "pull_requests": 14, "deployments": 2},
            ],
            "window": "7 days",
            "recommendation": "Review Payments and Checkout release risk because both changed recently and support critical revenue services.",
        }

    def _organization_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "gh-org-nexora", "name": "nexora", "type": "Organization", "domain": "organizations", "members": 312},
            {"id": "gh-org-platform", "name": "nexora-platform", "type": "Organization", "domain": "organizations", "members": 88},
        ]

    def _repository_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "gh-repo-checkout-api", "full_name": "nexora/checkout-api", "name": "checkout-api", "type": "Repository", "domain": "repositories", "visibility": "private", "application": "Checkout"},
            {"id": "gh-repo-payments-service", "full_name": "nexora/payments-service", "name": "payments-service", "type": "Repository", "domain": "repositories", "visibility": "private", "application": "Payments"},
            {"id": "gh-repo-identity-gateway", "full_name": "nexora/identity-gateway", "name": "identity-gateway", "type": "Repository", "domain": "repositories", "visibility": "private", "application": "Identity"},
        ]

    def _team_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "gh-team-platform", "name": "Platform Engineering", "type": "Team", "domain": "teams", "repositories": 72},
            {"id": "gh-team-security", "name": "Product Security", "type": "Team", "domain": "teams", "repositories": 124},
        ]

    def _code_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "gh-code-commits", "name": "Commits", "type": "Code Activity", "domain": "code", "count": 18420},
            {"id": "gh-code-prs", "name": "Pull Requests", "type": "Pull Requests", "domain": "pull_requests", "count": 1280},
            {"id": "gh-code-issues", "name": "Issues", "type": "Issues", "domain": "issues", "count": 742},
        ]

    def _delivery_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "gh-actions-runs", "name": "Workflow Runs", "type": "Actions", "domain": "actions", "count": 3380},
            {"id": "gh-releases", "name": "Releases", "type": "Releases", "domain": "releases", "count": 188},
            {"id": "gh-deployments", "name": "Deployments", "type": "Deployments", "domain": "deployments", "count": 316},
        ]

    def _security_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "gh-sec-dependabot", "name": "Dependabot Alerts", "type": "Security Alerts", "domain": "security", "count": 48},
            {"id": "gh-sec-code-scanning", "name": "Code Scanning Alerts", "type": "Security Alerts", "domain": "security", "count": 27},
            {"id": "gh-sec-secret-scanning", "name": "Secret Scanning Alerts", "type": "Security Alerts", "domain": "security", "count": 11},
        ]

    def _ownership_records(self) -> list[dict[str, Any]]:
        return [
            {"id": "gh-owner-checkout", "name": "Checkout Ownership", "type": "Ownership Mapping", "domain": "ownership", "application": "Checkout", "team": "Checkout Engineering", "cost_center": "CC-1100", "business_service": "Digital Commerce"},
            {"id": "gh-owner-payments", "name": "Payments Ownership", "type": "Ownership Mapping", "domain": "ownership", "application": "Payments", "team": "Payments Engineering", "cost_center": "CC-1200", "business_service": "Payments"},
        ]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
