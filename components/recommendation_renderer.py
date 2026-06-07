import json
from datetime import datetime, timedelta

import streamlit as st
from core.transformers import clean_api_response


def _clean_description_text(description):
    if isinstance(description, dict):
        findings = description.get("findings", ["Optimization opportunity identified."])
        return findings[0] if findings else "Optimization opportunity identified."

    clean_text = str(description)
    if clean_text.strip().startswith("{") and clean_text.strip().endswith("}"):
        parsed = clean_api_response(clean_text, default={})
        if isinstance(parsed, dict):
            findings = parsed.get("findings", ["Optimization opportunity identified."])
            return findings[0] if findings else "Optimization opportunity identified."
        return clean_text
    return clean_text


def render_recommendation_cards(
    items,
    label,
    priority,
    scope_key,
    *,
    money,
    priority_badge,
    service_icon,
    build_dynamic_actions,
    update_recommendation_fields,
    mark_recommendation_done,
):
    """Render recommendation cards with consistent actions and detail formatting."""
    st.markdown(f"### {label}")
    for rec in items:
        savings = rec.get("savings_monthly", rec.get("estimated_savings", 0)) or 0
        badge = str(priority_badge.get(priority, "⚪ Unknown"))
        service_name = str(rec.get("service") or "Service")
        rec_title = f"{service_icon(rec)} {service_name}"
        actions = build_dynamic_actions(rec)
        rec_status = str(rec.get("status") or "pending").strip().lower()
        owner_name = str(rec.get("assigned_to") or rec.get("owner") or "Unassigned")

        confidence = str(rec.get("confidence", "Medium")).strip()
        effort = str(rec.get("effort", "Medium")).strip()

        with st.container(border=True):
            header_col1, header_col2 = st.columns([2.5, 1.5])
            with header_col1:
                st.markdown(f"**{rec_title}**")
            with header_col2:
                st.markdown(
                    f"<div style='text-align: right; font-weight: 700; color: #0D8ABC; font-size: 1.1rem;'>{money(savings)}/mo</div>",
                    unsafe_allow_html=True,
                )

            fm1, fm2, fm3 = st.columns([1.2, 1, 1.3])
            fm1.caption(f"📊 Confidence: **{confidence}**")
            fm2.caption(f"⚙️ Effort: **{effort}**")
            fm3.caption(f"📌 Status: {rec_status.title()}")

            if rec.get("id") is not None:
                actor = str(st.session_state.get("username") or st.session_state.get("user_email") or "dashboard")
                default_owner = str(rec.get("assigned_to") or rec.get("owner") or "").strip()
                target_ids = rec.get("merged_ids") or [rec["id"]]

                def _run_action(payload, success_message, failure_message):
                    ok = update_recommendation_fields(target_ids, payload)
                    if ok:
                        st.success(success_message)
                        st.rerun()
                    st.warning(failure_message)

                control_col1, control_col2 = st.columns([1.2, 1])
                with control_col1:
                    assignee = st.text_input(
                        "Assignee",
                        value=default_owner,
                        key=f"assign-to-{scope_key}-{rec['id']}",
                        placeholder="owner username",
                    ).strip()
                with control_col2:
                    snooze_days = st.selectbox(
                        "Snooze days",
                        options=[3, 7, 14, 30],
                        index=1,
                        key=f"snooze-days-{scope_key}-{rec['id']}",
                    )

                action_cols = st.columns(7)
                if action_cols[0].button("Approve", key=f"approve-{scope_key}-{rec['id']}", use_container_width=True):
                    _run_action(
                        {
                            "status": "accepted",
                            "approved_at": datetime.utcnow().isoformat(),
                            "owner": assignee or default_owner or actor,
                        },
                        "Recommendation approved.",
                        "Approval did not complete. Please retry.",
                    )

                if action_cols[1].button("Reject", key=f"reject-{scope_key}-{rec['id']}", use_container_width=True):
                    _run_action(
                        {
                            "status": "dismissed",
                            "owner": assignee or default_owner or actor,
                        },
                        "Recommendation rejected.",
                        "Reject action did not complete. Please retry.",
                    )

                if action_cols[2].button("Snooze", key=f"snooze-{scope_key}-{rec['id']}", use_container_width=True):
                    snooze_until = (datetime.utcnow() + timedelta(days=int(snooze_days))).isoformat()
                    _run_action(
                        {
                            "status": "snoozed",
                            "snoozed_at": datetime.utcnow().isoformat(),
                            "snooze_until": snooze_until,
                            "owner": assignee or default_owner or actor,
                        },
                        f"Snoozed for {snooze_days} days.",
                        "Snooze action did not complete. Please retry.",
                    )

                if action_cols[3].button("Assign", key=f"assign-{scope_key}-{rec['id']}", use_container_width=True):
                    if not assignee:
                        st.warning("Enter an assignee before assigning.")
                    else:
                        _run_action(
                            {
                                "status": rec_status,
                                "owner": assignee,
                            },
                            f"Assigned to {assignee}.",
                            "Assign action did not complete. Please retry.",
                        )

                if action_cols[4].button("Escalate", key=f"escalate-{scope_key}-{rec['id']}", use_container_width=True):
                    escalation_owner = assignee or default_owner or actor
                    _run_action(
                        {
                            "status": "accepted" if rec_status in {"new", "pending", "snoozed", "dismissed"} else rec_status,
                            "owner": escalation_owner,
                            "approved_at": datetime.utcnow().isoformat(),
                        },
                        f"Escalated to {escalation_owner}.",
                        "Escalate action did not complete. Please retry.",
                    )

                if action_cols[5].button("Implement", key=f"implement-{scope_key}-{rec['id']}", use_container_width=True):
                    implementation_owner = assignee or default_owner or actor
                    _run_action(
                        {
                            "status": "in_progress",
                            "owner": implementation_owner,
                        },
                        "Moved to IN_PROGRESS.",
                        "Implement action did not complete. Please retry.",
                    )

                # --- Close Action ---
                if action_cols[6].button("Close", key=f"close-{scope_key}-{rec['id']}", use_container_width=True):
                    close_owner = assignee or default_owner or actor
                    _run_action(
                        {
                            "status": "closed",
                            "closed_at": datetime.utcnow().isoformat(),
                            "owner": close_owner,
                        },
                        "Recommendation closed.",
                        "Close action did not complete. Please retry.",
                    )

            with st.expander("📋 Details & Implementation Steps"):
                st.caption("**Top Actions:**")
                if actions:
                    for i, action in enumerate(actions[:5], 1):
                        st.write(f"• {action}")
                else:
                    st.caption("_No specific implementation steps available._")

                st.caption(f"**Owner:** {owner_name}")
                description = rec.get("recommendation") or rec.get("description") or rec.get("recommendation_text") or ""
                if description:
                    st.caption("**Description:**")
                    st.caption(_clean_description_text(description))

