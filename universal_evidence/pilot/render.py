"""Minimal Streamlit adapter over an already-governed Stage 1/2 view model."""

from universal_evidence.pilot.models import PilotVisibility


def render_pue_stage12(st, model):
    if model is None or model.visibility is PilotVisibility.HIDDEN:
        return
    with st.container(border=True):
        st.caption("DISCOVER & UNDERSTAND")
        if model.safe_message:
            st.info(model.safe_message)
            return
        st.subheader(model.evidence_heading)
        for item in model.evidence_items:
            st.markdown(f"**{item.label}** — {item.state_label}")
            if item.reason and item.state not in {"EVIDENCED", "OBSERVED"}:
                st.caption(item.reason)
        if model.capability_heading:
            st.subheader(model.capability_heading)
            for item in model.capability_items:
                st.markdown(f"**{item.label}** — {item.state_label}")
                if item.reason and item.state != "SUPPORTED":
                    st.caption(item.reason)
        if model.details:
            with st.expander("Evidence details"):
                st.write(f"Sources: {model.details.source_count}")
                st.write(f"Sheets: {model.details.sheet_count}")
                if model.details.record_count is not None:
                    st.write(f"Observed records: {model.details.record_count:,}")
                st.write(f"Governed mappings: {model.details.mapping_count}")
                st.write(
                    f"Normalization runs: {model.details.normalization_run_count}"
                )
