"""Development-pilot ACT-004 presentation; intentionally contains no business values."""

from universal_evidence.pilot.dev_control import valid_upload_scope
from universal_evidence.pilot.runtime import get_normalization_pilot_service
from universal_evidence.pilot.semantic_control import authenticated_confirmation_actor


def render_governed_normalization(st, admission) -> bool:
    if not valid_upload_scope(admission):
        return False
    try:
        actor = authenticated_confirmation_actor(st.session_state)
        model = get_normalization_pilot_service().experience(admission, actor=actor)
    except PermissionError:
        return False
    if model is None:
        return False
    with st.container(border=True):
        st.caption("VALIDATE DATA")
        st.subheader("Data Quality")
        eligible = sum(item.eligible for item in model.plan.items)
        st.caption(
            f"Governed fields: {eligible} | Blocked fields: {model.quality.blocked} | "
            f"Fields evaluated: {len(model.plan.items)}"
        )
        if model.executed:
            st.caption(
                f"Normalized observations: {model.observation_count} | "
                f"Valid: {model.quality.valid} | Invalid: {model.quality.invalid} | "
                f"Missing: {model.quality.missing} | Unsupported: {model.quality.unsupported}"
            )
            if model.currency_partitions:
                st.caption("Currency partitions: " + ", ".join(model.currency_partitions))
        else:
            st.caption("Execution is unavailable until the capability-visible pilot stage.")
        st.warning(f"Total Cost: {model.total_cost_state} - {model.total_cost_reason}")
        st.caption("Only governed, valid observations can support analysis.")
    return True
