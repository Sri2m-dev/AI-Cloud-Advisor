from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_intelligence import enterprise_intelligence_service, enterprise_search_service


def enterprise_ai_copilot(context, *, role, providers=None, **configuration):
    intelligence = enterprise_intelligence_service(context, role=role, **configuration)
    search = enterprise_search_service(context, role=role, **configuration)
    return EnterpriseAIOrchestrator(search=search, intelligence=intelligence, providers=providers)
