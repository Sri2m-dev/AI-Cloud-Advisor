"""Runtime composition for governed Enterprise Scenario Intelligence."""

from services.enterprise_registry_composition import enterprise_registry_service
from services.relationship_intelligence_composition import relationship_intelligence_service

from .service import ScenarioService


def enterprise_scenario_service(
    context,
    *,
    role,
    policy_previewer=None,
    **configuration,
):
    """Compose read-only scenario intelligence over the canonical P4.3 stores."""

    registry = enterprise_registry_service(context, role=role, **configuration)
    relationships = relationship_intelligence_service(context, role=role, **configuration)
    return ScenarioService(
        context,
        role=role,
        registry=registry,
        relationships=relationships,
        policy_previewer=policy_previewer,
    )
