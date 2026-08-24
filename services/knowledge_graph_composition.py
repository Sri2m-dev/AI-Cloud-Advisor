"""Compose canonical registry and relationship intelligence into enterprise knowledge."""

from __future__ import annotations

from enterprise_registry.knowledge_graph import EnterpriseKnowledgeGraphService
from services.enterprise_registry_composition import enterprise_registry_service
from services.relationship_intelligence_composition import relationship_intelligence_service


def enterprise_knowledge_graph_service(context, *, role, **configuration):
    registry = enterprise_registry_service(context, role=role, **configuration)
    relationships = relationship_intelligence_service(context, role=role, **configuration)
    return EnterpriseKnowledgeGraphService(registry, relationships)
