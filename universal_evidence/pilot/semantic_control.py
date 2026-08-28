"""Authenticated development-only Streamlit control for ACT-003 decisions."""

from __future__ import annotations

from universal_evidence.governance import ActorType, ConfirmationActor
from universal_evidence.pilot.dev_control import dev_control_enabled, valid_upload_scope
from universal_evidence.pilot.runtime import get_semantic_pilot_service


def authenticated_confirmation_actor(session_state) -> ConfirmationActor:
    user = session_state.get("user")
    user_email = user.get("email") if isinstance(user, dict) else user
    actor_id = str(
        session_state.get("user_id")
        or session_state.get("email")
        or user_email
        or ""
    ).strip()
    role = str(session_state.get("role") or "").strip()
    if not actor_id or not role:
        raise PermissionError("authenticated actor identity is required")
    return ConfirmationActor(actor_id, actor_id, role, ActorType.HUMAN)


def render_semantic_governance(st, admission) -> bool:
    if not valid_upload_scope(admission):
        return False
    try:
        actor = authenticated_confirmation_actor(st.session_state)
        model = get_semantic_pilot_service().experience(admission, actor=actor)
    except PermissionError:
        return False
    if model is None:
        return False

    with st.container(border=True):
        st.caption("GOVERNED SEMANTIC MAPPING - PILOT")
        st.subheader("Observed field meanings")
        st.caption(
            "Candidates are evidence-backed hypotheses. Only an effective governed decision "
            "is authoritative."
        )
        for mapping in model.mappings:
            with st.expander(f"{mapping.source_column_name} - {mapping.status.value}"):
                if mapping.effective_display_name:
                    st.markdown(f"**Governed as:** {mapping.effective_display_name}")
                st.caption(mapping.status_reason)
                for candidate in mapping.candidates:
                    st.markdown(
                        f"**Candidate:** {candidate.display_name}  "
                        f"\nConfidence: {candidate.confidence_band} "
                        f"({candidate.confidence_percent}%)"
                    )
                    st.caption(candidate.explanation)
                if dev_control_enabled():
                    _render_actions(st, admission, mapping, actor)
                if mapping.history:
                    st.caption(f"Governance history: {len(mapping.history)} immutable decision(s)")
        st.caption(
            f"Candidates: {model.candidate_count} | "
            f"Confirmation required: {model.confirmation_required_count} | "
            f"Effective mappings: {model.effective_mapping_count}"
        )
    return True


def _render_actions(st, admission, mapping, actor) -> None:
    service = get_semantic_pilot_service()
    reason_key = f"pue_semantic_reason_{mapping.column_reference}"
    reason = st.text_input(
        "Governance reason",
        key=reason_key,
        help="Required for rejection and override.",
    )
    candidate = mapping.candidates[0] if mapping.candidates else None
    actions = st.columns(3)
    if candidate and "confirm" in mapping.allowed_actions:
        if actions[0].button(
            "Confirm",
            key=f"pue_semantic_confirm_{mapping.column_reference}",
            use_container_width=True,
        ):
            _apply(st, lambda: service.confirm(
                admission, mapping.column_reference, candidate.concept_id, actor=actor
            ))
    if candidate and "reject" in mapping.allowed_actions:
        if actions[1].button(
            "Reject",
            key=f"pue_semantic_reject_{mapping.column_reference}",
            use_container_width=True,
        ):
            _apply(st, lambda: service.reject(
                admission,
                mapping.column_reference,
                candidate.concept_id,
                actor=actor,
                reason=reason,
            ))
    if "override" in mapping.allowed_actions:
        labels = {label: concept_id for concept_id, label in mapping.approved_override_concepts}
        selected = st.selectbox(
            "Approved override concept",
            tuple(labels),
            key=f"pue_semantic_override_target_{mapping.column_reference}",
        )
        if actions[2].button(
            "Override",
            key=f"pue_semantic_override_{mapping.column_reference}",
            use_container_width=True,
        ):
            _apply(st, lambda: service.override(
                admission,
                mapping.column_reference,
                labels[selected],
                actor=actor,
                reason=reason,
            ))


def _apply(st, action) -> None:
    try:
        action()
    except (PermissionError, ValueError) as exc:
        st.error(str(exc))
        return
    st.rerun()
