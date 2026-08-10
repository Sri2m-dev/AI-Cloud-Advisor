"""Operations Workspace application service."""

from repositories.operations_workspace_repository import OperationsWorkspaceRepository
from services.operations_workspace_composition import operations_workspace_repository


class OperationsWorkspaceService:
    def __init__(self, repository: OperationsWorkspaceRepository | None = None) -> None:
        self.repository = repository or operations_workspace_repository()

    def get_approval_requests(self, organization_id):
        return self.repository.get_approval_requests(organization_id) or []

    def get_recommendations(self, organization_id):
        return self.repository.get_recommendations(organization_id) or []

    def get_audit_events(self, organization_id):
        return self.repository.get_audit_events(organization_id) or []

    def get_cost_anomalies(self, organization_id):
        return self.repository.get_cost_anomalies(organization_id) or []

    def get_cloud_costs(self, organization_id):
        return self.repository.get_cloud_costs(organization_id) or []

    def get_summary(self, organization_id):
        return {
            "approvals": len(self.get_approval_requests(organization_id)),
            "recommendations": len(self.get_recommendations(organization_id)),
            "anomalies": len(self.get_cost_anomalies(organization_id)),
            "audit_events": len(self.get_audit_events(organization_id)),
        }
