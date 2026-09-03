from __future__ import annotations

from services.enterprise_spend_service import EnterpriseSpendService
from universal_evidence.financial.governance import (
    FinancialDecisionKind,
    FinancialDecisionState,
    FinancialGovernanceError,
)
from universal_evidence.financial.production import configured_governed_financial_workflow

_CURRENCIES = ("USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD")


def render_financial_governance(st, admission, *, context, actor_id, actor_role):
    """Render the bounded production authority and explicit publication workflow."""
    workflow = configured_governed_financial_workflow()
    if workflow is None:
        st.info("Durable financial governance is unavailable until persistence is configured.")
        return
    result = workflow.analyze(admission)
    domain = workflow.effective(admission, FinancialDecisionKind.DOMAIN)
    measure = workflow.effective(admission, FinancialDecisionKind.SEMANTIC_MEASURE)
    currency = workflow.effective(admission, FinancialDecisionKind.CURRENCY)
    st.markdown("### Financial authority")
    st.caption("Governed proposals are scoped to this evidence and persist across restart.")
    st.write(
        {
            "Domain": result.domain.domain.value,
            "Domain confidence": result.domain.confidence.value,
            "Domain authority": domain.state.value if domain else "REQUIRED",
            "Measure authority": measure.state.value if measure else "REQUIRED",
            "Currency authority": currency.state.value if currency else "REQUIRED",
            "Capability": "EXECUTABLE" if result.authorized else "BLOCKED",
        }
    )
    key = admission.fingerprint[:12]
    if currency is None or currency.state is FinancialDecisionState.REJECTED:
        selected = st.selectbox("Financial currency", _CURRENCIES, key=f"fin_currency_{key}")
        confirmed = st.checkbox(
            "I confirm this currency applies to the governed financial evidence.",
            key=f"fin_currency_confirm_{key}",
        )
        if st.button("Confirm financial currency", key=f"fin_currency_submit_{key}"):
            if not confirmed:
                st.error("Explicit confirmation is required.")
            else:
                workflow.decide(
                    admission,
                    FinancialDecisionKind.CURRENCY,
                    FinancialDecisionState.CONFIRMED,
                    selected,
                    actor_id=actor_id,
                    actor_role=actor_role,
                )
                st.rerun()
    if currency and currency.state is not FinancialDecisionState.REJECTED:
        with st.expander("Reject or override financial currency"):
            replacement = st.selectbox(
                "Override currency", _CURRENCIES, key=f"fin_currency_override_{key}"
            )
            reason = st.text_input("Governance reason", key=f"fin_currency_reason_{key}")
            left, right = st.columns(2)
            if left.button("Reject currency", key=f"fin_currency_reject_{key}"):
                try:
                    workflow.decide(
                        admission,
                        FinancialDecisionKind.CURRENCY,
                        FinancialDecisionState.REJECTED,
                        currency.value,
                        actor_id=actor_id,
                        actor_role=actor_role,
                        reason=reason,
                    )
                    st.rerun()
                except FinancialGovernanceError as exc:
                    st.error(str(exc))
            if right.button("Override currency", key=f"fin_currency_override_submit_{key}"):
                try:
                    workflow.decide(
                        admission,
                        FinancialDecisionKind.CURRENCY,
                        FinancialDecisionState.OVERRIDDEN,
                        replacement,
                        actor_id=actor_id,
                        actor_role=actor_role,
                        reason=reason,
                    )
                    st.rerun()
                except FinancialGovernanceError as exc:
                    st.error(str(exc))
    if result.authorized:
        if st.button("Publish governed financial observations", key=f"fin_publish_{key}"):
            published = workflow.publish(admission, context)
            st.success(f"Published {len(published.observations):,} governed observations.")
        posture = EnterpriseSpendService(
            workflow.publication_repository, cache_ttl_seconds=0
        ).get_financial_posture(context)
        if posture.has_data:
            st.caption("Enterprise Spend publication is active for this governed analysis.")
