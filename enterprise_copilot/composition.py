from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_intelligence import enterprise_intelligence_service, enterprise_search_service
from enterprise_scenario import enterprise_scenario_service
from services.enterprise_registry_composition import enterprise_registry_service
from services.enterprise_spend_composition import enterprise_spend_service
from services.relationship_intelligence_composition import relationship_intelligence_service
from universal_evidence.pilot.governed_intelligence import GovernedAskNexoraService


def enterprise_ai_copilot(context, *, role, providers=None, **configuration):
    intelligence = enterprise_intelligence_service(context, role=role, **configuration)
    search = enterprise_search_service(context, role=role, **configuration)
    scenarios = enterprise_scenario_service(context, role=role, **configuration)
    registry = enterprise_registry_service(context, role=role, **configuration)
    relationships = relationship_intelligence_service(context, role=role, **configuration)
    return EnterpriseAIOrchestrator(
        search=search,
        intelligence=intelligence,
        providers=providers,
        scenario_service=scenarios,
        governed_ask=GovernedAskNexoraService(
            registry=registry,
            graph=relationships,
            financial_service=enterprise_spend_service(),
            financial_context=context,
        ),
    )
