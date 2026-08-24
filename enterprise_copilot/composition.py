from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_intelligence import enterprise_intelligence_service, enterprise_search_service
from enterprise_scenario import enterprise_scenario_service


def enterprise_ai_copilot(context, *, role, providers=None, **configuration):
    intelligence = enterprise_intelligence_service(context, role=role, **configuration)
    search = enterprise_search_service(context, role=role, **configuration)
    scenarios = enterprise_scenario_service(context, role=role, **configuration)
    return EnterpriseAIOrchestrator(
        search=search,
        intelligence=intelligence,
        providers=providers,
        scenario_service=scenarios,
    )
