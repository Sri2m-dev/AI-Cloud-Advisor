from __future__ import annotations

import os

from services.universal_evidence_runtime_service import initialize_universal_evidence_runtime
from universal_evidence.financial.governance import GovernedFinancialWorkflow
from universal_evidence.financial.publication import CanonicalFinancialRepository


def configured_governed_financial_workflow(database=None):
    """Compose persisted governance and publication on the configured durable runtime."""
    configured = database or os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB")
    runtime = initialize_universal_evidence_runtime(configured)
    if runtime is None:
        return None
    return GovernedFinancialWorkflow(
        runtime.lifecycle, CanonicalFinancialRepository(configured)
    )
