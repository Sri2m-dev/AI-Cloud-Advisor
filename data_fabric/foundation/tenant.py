"""Tenant context helpers for Data Fabric isolation boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data_fabric.foundation.exceptions import (
    DataFabricTenantBoundaryError,
    DataFabricValidationError,
)


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Organization and tenant partition carried across orchestration."""

    organization_id: str
    tenant_id: str

    def __post_init__(self) -> None:
        if not self.organization_id:
            raise DataFabricValidationError("organization_id is required")
        if not self.tenant_id:
            raise DataFabricValidationError("tenant_id is required")

    def to_serializable(self) -> dict[str, str]:
        """Return deterministic JSON-compatible tenant context."""

        return {"organization_id": self.organization_id, "tenant_id": self.tenant_id}

    def assert_matches(self, other: TenantContext, label: str = "tenant_context") -> None:
        """Raise when two tenant contexts cross a tenant boundary."""

        if self != other:
            raise DataFabricTenantBoundaryError(f"{label} crosses tenant boundary")

    def assert_record_matches(self, record: Any, label: str = "record") -> None:
        """Validate a record exposes matching organization and tenant fields."""

        organization_id = getattr(record, "organization_id", None)
        tenant_id = getattr(record, "tenant_id", None)
        if organization_id != self.organization_id or tenant_id != self.tenant_id:
            raise DataFabricTenantBoundaryError(f"{label} crosses tenant boundary")
