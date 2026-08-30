"""Bounded ACT-005 development UI; no natural-language execution route."""

from decimal import Decimal

from universal_evidence.aggregation import AggregationResultStatus
from universal_evidence.pilot.dev_control import valid_upload_scope
from universal_evidence.pilot.runtime import get_measurement_pilot_service
from universal_evidence.pilot.semantic_control import authenticated_confirmation_actor
from universal_evidence.planning import AnalyticalIntentType


def render_governed_measurement(st, admission) -> bool:
    if not valid_upload_scope(admission):
        return False
    try:
        actor = authenticated_confirmation_actor(st.session_state)
        service = get_measurement_pilot_service()
        model = service.readiness(admission, actor=actor)
    except PermissionError:
        return False
    if model is None:
        return False
    with st.container(border=True):
        st.caption("REVIEW AVAILABLE INSIGHTS")
        st.subheader("What Nexora can answer now")
        st.caption(
            f"State: {model.state} | Currency ready: {'Yes' if model.currency_ready else 'No'} | "
            f"Operations: {', '.join(model.available_operations) or 'None'}"
        )
        for reason in model.reasons:
            st.warning(reason)
        if "COUNT" in model.available_operations and st.button(
            "Run Record Count", key="act005_count"
        ):
            _execute(st, service, admission, actor, AnalyticalIntentType.COUNT_RECORDS)
        monetary = tuple(item for item in model.measure_concepts if item.startswith("financial."))
        if "SUM" in model.available_operations and monetary:
            selected = st.selectbox("Governed measure", monetary, key="act005_measure")
            if st.button("Authorize Total Cost Calculation", key="act005_sum"):
                _execute(
                    st,
                    service,
                    admission,
                    actor,
                    AnalyticalIntentType.TOTAL_MEASURE,
                    measure_concept_id=selected,
                )
            groupable = tuple(
                item for item in model.dimension_concepts if item != "financial.currency"
            )
            if "GROUPED_SUM" in model.available_operations and groupable:
                dimension = st.selectbox(
                    "Governed grouping dimension", groupable, key="act005_dimension"
                )
                if st.button("Calculate governed grouped total", key="act005_grouped_sum"):
                    _execute(
                        st,
                        service,
                        admission,
                        actor,
                        AnalyticalIntentType.GROUP_MEASURE_BY_DIMENSION,
                        measure_concept_id=selected,
                        dimension_concept_ids=(dimension,),
                    )
        _render_result(
            st,
            st.session_state.get("act005_result"),
            admission.fingerprint,
            lambda: service.record_result_viewed(admission, actor=actor),
            lambda planning, result: service.result_is_current(
                admission, planning, result, actor=actor
            ),
        )
        st.caption("Execution is limited to the certified operations shown above.")
    return True


def _execute(
    st,
    service,
    admission,
    actor,
    intent_type,
    measure_concept_id=None,
    dimension_concept_ids=(),
):
    planning, result = service.execute(
        admission,
        actor=actor,
        intent_type=intent_type,
        measure_concept_id=measure_concept_id,
        dimension_concept_ids=dimension_concept_ids,
    )
    st.session_state["act005_result"] = (admission.fingerprint, planning, result)
    st.rerun()


def _render_result(st, stored, admission_fingerprint, record_view, is_current):
    if not stored or len(stored) != 3:
        return
    stored_fingerprint, planning, result = stored
    if stored_fingerprint != admission_fingerprint:
        return
    if result is not None and not is_current(planning, result):
        st.warning("Prior result is stale and has been suppressed.")
        return
    if result is None:
        reasons = ", ".join(item.value for item in planning.plan.reason_codes)
        st.warning("Execution blocked: " + reasons)
        return
    if result.status is not AggregationResultStatus.COMPLETED:
        st.warning("Execution blocked: " + ", ".join(item.value for item in result.warnings))
        return
    if result.groups:
        st.dataframe(
            [
                {
                    "Group": " / ".join(str(value) for _, value in group.dimension_values),
                    "Value": str(group.value),
                    "Currency": group.unit,
                    "Records": group.record_count,
                }
                for group in result.groups
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        value = result.scalar_value
        display = f"{value:,}" if isinstance(value, (int, Decimal)) else str(value)
        if result.currency_or_unit:
            display = f"{result.currency_or_unit} {display}"
        st.metric("Governed result", display)
    st.caption(
        f"Records used: {result.statistics.included_records} | "
        f"Invalid excluded: {result.statistics.excluded_invalid_records} | "
        f"Plan: {result.plan_id} | Result: {result.result_id}"
    )
    record_view()
