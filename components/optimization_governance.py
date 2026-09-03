from __future__ import annotations

from universal_evidence.optimization import OpportunityState
from universal_evidence.optimization.production import configured_optimization_authority
from universal_evidence.persistence import LifecycleScope

AUTHORIZED_ROLES = {"super_admin", "client_admin", "cio", "executive", "admin"}


class OptimizationGovernanceController:
    def __init__(self, governance, publication):
        self.governance = governance
        self.publication = publication

    def act(self, item, action, *, context, actor_id, actor_role, reason):
        if actor_role not in AUTHORIZED_ROLES:
            raise PermissionError("role cannot govern optimization opportunities")
        target = {
            "APPROVE": OpportunityState.APPROVED,
            "REJECT": OpportunityState.REJECTED,
            "REQUEST_REVISION": OpportunityState.REVISION_REQUIRED,
        }.get(action)
        if target is None:
            raise ValueError("unsupported governance action")
        if (
            target in {OpportunityState.REJECTED, OpportunityState.REVISION_REQUIRED}
            and not reason.strip()
        ):
            raise ValueError("rejection and revision require a reason")
        scope = LifecycleScope(
            item.organization_id, item.tenant_id, item.prospect_id, item.analysis_id
        )
        current = item
        if current.state is OpportunityState.ELIGIBLE:
            current = self.governance.transition(
                scope,
                current.opportunity_id,
                OpportunityState.PROPOSED,
                actor_id=actor_id,
                actor_role=actor_role,
                reason="submitted for governed review",
            )
        if current.state is OpportunityState.PROPOSED:
            current = self.governance.transition(
                scope,
                current.opportunity_id,
                OpportunityState.UNDER_REVIEW,
                actor_id=actor_id,
                actor_role=actor_role,
                reason="opened by authorized reviewer",
            )
        updated = self.governance.transition(
            scope,
            current.opportunity_id,
            target,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason or f"authorized {action.lower()}",
        )
        self.publication.publish(updated, context)
        return updated


def render_optimization_governance(st, *, context, actor_id, actor_role, database=None):
    governance, publication = configured_optimization_authority(database)
    controller = OptimizationGovernanceController(governance, publication)
    items = publication.list(context)
    st.subheader("Governed optimization opportunities")
    if not items:
        st.info("No canonical optimization opportunities are available.")
        return ()
    for item in items:
        with st.container(border=True):
            st.markdown(f"### {item.opportunity_type.value.replace('_', ' ').title()}")
            st.write(f"Affected entity: {item.affected_entity}")
            cols = st.columns(4)
            cols[0].metric(
                "Current cost",
                str(item.current_cost) if item.current_cost is not None else "UNKNOWN",
            )
            cols[1].metric(
                "Potential savings",
                str(item.potential_savings) if item.potential_savings is not None else "UNKNOWN",
            )
            cols[2].metric(
                "Currency / period",
                f"{item.currency or 'UNKNOWN'} / {item.cost_period or 'UNKNOWN'}",
            )
            cols[3].metric("Lifecycle", item.state.value)
            st.write(f"Recommendation: {item.recommendation}")
            st.write(f"Calculation model: {item.calculation_model or 'UNKNOWN'}")
            st.write(
                {
                    "inputs": dict(item.calculation_inputs),
                    "assumptions": item.calculation_assumptions,
                }
            )
            st.write(
                {
                    "evidence": item.evidence_references,
                    "confidence": item.confidence_score,
                    "factors": dict(item.confidence_factors),
                }
            )
            st.write(
                {
                    "technical_risk": item.technical_risk.value,
                    "business_risk": item.business_risk.value,
                    "effort": item.effort.value,
                    "alternatives": item.alternatives,
                }
            )
            if actor_role in AUTHORIZED_ROLES and item.state in {
                OpportunityState.ELIGIBLE,
                OpportunityState.PROPOSED,
                OpportunityState.UNDER_REVIEW,
            }:
                reason = st.text_input(
                    "Decision reason", key=f"optimization_reason_{item.opportunity_id}"
                )
                for action in ("APPROVE", "REJECT", "REQUEST_REVISION"):
                    if st.button(
                        action.replace("_", " ").title(),
                        key=f"optimization_{action}_{item.opportunity_id}",
                    ):
                        controller.act(
                            item,
                            action,
                            context=context,
                            actor_id=actor_id,
                            actor_role=actor_role,
                            reason=reason,
                        )
                        st.rerun()
    return items
