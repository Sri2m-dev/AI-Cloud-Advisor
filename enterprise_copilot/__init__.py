"""Enterprise Copilot public package boundary.

Composition is imported lazily so semantic-planner contracts can be imported
without recursively loading the production composition graph.
"""

from enterprise_copilot.models import *  # noqa: F403
from enterprise_copilot.orchestrator import EnterpriseAIOrchestrator


def enterprise_ai_copilot(*args, **kwargs):
    from enterprise_copilot.composition import enterprise_ai_copilot as compose

    return compose(*args, **kwargs)


__all__ = ["EnterpriseAIOrchestrator", "enterprise_ai_copilot"]
