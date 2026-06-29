"""
Operations Workspace Service
"""

from repositories.operations_workspace_repository import (
    OperationsWorkspaceRepository,
)


class OperationsWorkspaceService:

    @staticmethod
    def get_summary():
        return OperationsWorkspaceRepository.get_summary()

    @staticmethod
    def get_approval_requests():
        return OperationsWorkspaceRepository.get_approval_requests() or []

    @staticmethod
    def get_recommendations():
        return OperationsWorkspaceRepository.get_recommendations() or []

    @staticmethod
    def get_audit_events():
        return OperationsWorkspaceRepository.get_audit_events() or []

    @staticmethod
    def get_cost_anomalies():
        return OperationsWorkspaceRepository.get_cost_anomalies() or []

    @staticmethod
    def get_cloud_costs():
        return OperationsWorkspaceRepository.get_cloud_costs() or []