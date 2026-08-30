"""Small dependency-injected bridge used by production workflow boundaries."""

from __future__ import annotations

from dataclasses import replace

from universal_evidence.operations.models import OperationContext


def workflow_context(base: OperationContext | None, scope=None, *, actor=None, actor_id=None):
    if base is None:
        return None
    values = {}
    if scope is not None:
        values.update(
            organization_id=getattr(scope, "organization_id", None) or base.organization_id,
            tenant_id=getattr(scope, "tenant_id", None) or base.tenant_id,
            prospect_id=getattr(scope, "prospect_id", None) or base.prospect_id,
            analysis_id=getattr(scope, "analysis_id", None) or base.analysis_id,
        )
    if actor is not None:
        values["actor_id"] = getattr(actor, "actor_id", None)
        values["actor_role"] = getattr(actor, "actor_role", None)
    elif actor_id is not None:
        values["actor_id"] = actor_id
    return replace(base, **values)


def observe(operations, event_type, context, **kwargs):
    """Emit when configured; the operations service owns audit failure policy."""
    if operations is None or context is None:
        return None
    return operations.emit(event_type, context, **kwargs)
