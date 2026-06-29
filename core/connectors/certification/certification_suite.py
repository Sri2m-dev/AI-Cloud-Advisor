from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ConnectorCertificationSuite:
    name: str = "Enterprise Connector Certification"
    required_capabilities: tuple[str, ...] = (
        "connect",
        "discover",
        "sync_entities",
        "sync_relationships",
        "sync_metadata",
        "health_check",
    )
    required_fabric_hooks: tuple[str, ...] = (
        "sync_entities",
        "sync_relationships",
        "sync_metadata",
    )
    minimum_health_score: float = 80.0
    maximum_error_count: int = 0
    required_successful_operations: tuple[str, ...] = (
        "discover",
        "sync_entities",
        "sync_metadata",
    )
    metadata: dict = field(default_factory=dict)
