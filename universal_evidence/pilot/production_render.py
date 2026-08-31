"""Streamlit rendering for ACT-010B production view models."""

from __future__ import annotations

from universal_evidence.pilot.production_views import (
    RECONCILIATION_MUTATION_ROLES,
    confirm_reconciliation,
    reject_reconciliation,
)


def render_enterprise_context(st, model) -> None:
    st.markdown("### Enterprise Context")
    if not model.entities:
        st.info(model.empty_message)
        return
    columns = st.columns(min(5, len(model.counts)))
    for column, (label, count) in zip(columns, model.counts, strict=True):
        column.metric(label, count)
    for entity in model.entities:
        with st.expander(f"{entity.entity_type_label}: {entity.name}"):
            st.write(f"**Type:** {entity.entity_type_label}")
            st.write(f"**Governance:** {entity.governance_state}")
            st.write(f"**Source evidence:** {entity.source_count}")
            if entity.sources:
                st.caption("Sources: " + ", ".join(entity.sources))
            for relationship in entity.relationships:
                st.write(f"→ {relationship.relationship} {relationship.target_name}")


def render_reconciliation(st, model, *, controls=None, authorization=None) -> None:
    st.markdown("### Source Reconciliation")
    if not model.items:
        st.info(model.empty_message)
        return
    for item in model.items:
        with st.container(border=True):
            st.markdown(f"**{item.entity_type}: {item.canonical_name}**")
            if item.status == "Conflict":
                st.warning("Conflict — review required")
            elif item.status == "Needs Review":
                st.warning("Possible match — review required")
            else:
                st.write(f"**Status:** {item.status}")
            if item.sources:
                st.write("**Contributing sources:** " + ", ".join(item.sources))
            st.caption(item.match_basis)
            for field, values in item.conflicts:
                st.write(f"**{field} conflict**")
                for source, value in values:
                    st.write(f"- {source}: {value}")
            _render_decision_actions(st, item, controls, authorization=authorization)


def _render_decision_actions(st, item, controls, *, authorization):
    role = authorization.role if authorization is not None else ""
    if (
        controls is None
        or item.status != "Needs Review"
        or role not in RECONCILIATION_MUTATION_ROLES
        or not item.proposal_fingerprint
    ):
        return
    service, proposals = controls
    proposal = proposals.get(item.proposal_fingerprint)
    if proposal is None:
        return
    reason = st.text_input(
        "Review reason",
        key=f"act010b_reconciliation_reason_{item.proposal_fingerprint}",
    )
    target_by_label = {name: canonical_id for canonical_id, name in item.valid_targets}
    selected = None
    if target_by_label:
        selected = st.selectbox(
            "Canonical target",
            tuple(target_by_label),
            key=f"act010b_reconciliation_target_{item.proposal_fingerprint}",
        )
    actions = st.columns(2)
    if selected and actions[0].button(
        "Confirm Match",
        key=f"act010b_confirm_{item.proposal_fingerprint}",
        use_container_width=True,
    ):
        try:
            confirm_reconciliation(
                service,
                proposal,
                canonical_id=target_by_label[selected],
                authorization=authorization,
                reason=reason,
            )
        except (PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()
    if actions[1].button(
        "Reject Match",
        key=f"act010b_reject_{item.proposal_fingerprint}",
        use_container_width=True,
    ):
        try:
            reject_reconciliation(
                service,
                proposal,
                authorization=authorization,
                reason=reason,
            )
        except (PermissionError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.rerun()
