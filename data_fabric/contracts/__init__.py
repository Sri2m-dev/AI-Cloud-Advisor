"""Canonical Enterprise Data Fabric contracts."""

from data_fabric.contracts.entity import EnterpriseEntity
from data_fabric.contracts.enums import EntityType, RelationshipType
from data_fabric.contracts.identity import EntityIdentity
from data_fabric.contracts.lineage import EntityLineage
from data_fabric.contracts.ownership import EntityOwnership
from data_fabric.contracts.provenance import EntityProvenance
from data_fabric.contracts.quality import EntityQuality
from data_fabric.contracts.relationship import EnterpriseRelationship
from data_fabric.contracts.versioning import EntityVersion

__all__ = [
    "EnterpriseEntity",
    "EnterpriseRelationship",
    "EntityIdentity",
    "EntityLineage",
    "EntityOwnership",
    "EntityProvenance",
    "EntityQuality",
    "EntityVersion",
    "EntityType",
    "RelationshipType",
]
