from auth.authenticated_tenant import AuthenticatedTenantContext
from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator
from enterprise_intelligence import enterprise_intelligence_service, enterprise_search_service
from enterprise_scenario import enterprise_scenario_service
from enterprise_scenario.service import READ_ROLES as SCENARIO_READ_ROLES
from services.canonical_optimization_service import CanonicalOptimizationService
from services.enterprise_intelligence_query_service import EnterpriseIntelligenceQueryService
from services.enterprise_registry_composition import enterprise_registry_service
from services.enterprise_spend_composition import enterprise_spend_service
from services.governed_source_capabilities import GovernedSourceCapabilities
from services.relationship_intelligence_composition import relationship_intelligence_service
from universal_evidence.pilot.governed_intelligence import GovernedAskNexoraService


def enterprise_ai_copilot(context, *, role, providers=None, **configuration):
    financial_context = configuration.pop("financial_context", context)
    intelligence = enterprise_intelligence_service(context, role=role, **configuration)
    search = enterprise_search_service(context, role=role, **configuration)
    # Scenario access is optional; its narrower policy must not block authorized Ask reads.
    scenarios = (
        enterprise_scenario_service(context, role=role, **configuration)
        if role in SCENARIO_READ_ROLES
        else None
    )
    registry = enterprise_registry_service(context, role=role, **configuration)
    relationships = relationship_intelligence_service(context, role=role, **configuration)
    try:
        optimization = CanonicalOptimizationService()
    except RuntimeError:
        optimization = None
    query_service = EnterpriseIntelligenceQueryService(
        financial_service=enterprise_spend_service(),
        financial_context=financial_context,
        optimization_service=optimization,
        relationship_service=relationships,
        registry=registry,
    )
    return EnterpriseAIOrchestrator(
        search=search,
        intelligence=intelligence,
        providers=providers,
        scenario_service=scenarios,
        source_capabilities=(
            GovernedSourceCapabilities(financial_context)
            if isinstance(financial_context, AuthenticatedTenantContext)
            else None
        ),
        governed_ask=GovernedAskNexoraService(
            registry=registry,
            graph=relationships,
            financial_service=enterprise_spend_service(),
            financial_context=financial_context,
            intelligence_service=query_service,
        ),
    )
