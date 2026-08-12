from enterprise_intelligence.service import EnterpriseIntelligenceService
from services.knowledge_graph_composition import enterprise_knowledge_graph_service


def enterprise_intelligence_service(context, *, role, limits=None, **configuration):
    graph = enterprise_knowledge_graph_service(context, role=role, **configuration)
    return EnterpriseIntelligenceService(context, role=role, graph=graph, limits=limits)
