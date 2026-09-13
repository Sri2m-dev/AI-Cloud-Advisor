"""Organization & Team Administration page.

Allows authorized tenant administrators to manage organization identity,
invite team members, review/revoke pending invitations, and track first-run
readiness.
"""

from __future__ import annotations

import streamlit as st

from auth.role_constants import ROLES, normalize_role
from components.sidebar_navigation import render_sidebar_navigation
from services.onboarding_service import (
    AuthorizationError,
    OnboardingError,
    create_invitation,
    get_invitations,
    is_clean_workspace,
    revoke_invitation,
)
from shared.auth import require_role
from shared.session import init_session
from shared.styles import configure_page

configure_page(page_title="Nexora | Organization & Team", page_icon="🏢")
init_session()
require_role(["client_admin", "super_admin", "admin"])
role = normalize_role(st.session_state.get("role"))
render_sidebar_navigation(role)

st.title("Organization & Team Administration")
st.caption("Governed tenant management, team provisioning, and workspace readiness")

user_email = str(st.session_state.get("email") or "").strip()
org_id = str(st.session_state.get("organization_id") or "").strip()
org_name = str(st.session_state.get("organization_name") or "Enterprise Workspace").strip()

# Organization Identity Card
st.markdown("### Organization Identity")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Organization Name", value=org_name)
with col2:
    st.metric(label="Tenant ID", value=org_id[:8] + "..." if len(org_id) > 8 else org_id)
with col3:
    st.metric(label="Your Role", value=role.replace("_", " ").title())

st.divider()

# First-run Workspace Readiness Banner
if is_clean_workspace(org_id):
    st.info(
        "🚀 **Clean Workspace Initialized:** This organization has no data sources connected.\n\n"
        "Next Action: Upload a billing file or configure a cloud connector.",
        icon="ℹ️",
    )
    if st.button("Go to Data Sources & Connectors", key="btn_goto_connectors"):
        st.switch_page("pages/data_sources_connectors.py")

st.markdown("### Invite Team Member")
with st.form("invite_user_form", clear_on_submit=True):
    col_email, col_role, col_days = st.columns([3, 2, 1])
    with col_email:
        invite_email = st.text_input("Member Email", placeholder="colleague@company.com")
    with col_role:
        available_roles = [r for r in ROLES if r != "super_admin" or role == "super_admin"]
        invite_role = st.selectbox(
            "Assigned Role",
            options=available_roles,
            format_func=lambda x: x.replace("_", " ").title(),
            index=available_roles.index("executive") if "executive" in available_roles else 0,
        )
    with col_days:
        expiry_days = st.number_input("Expiry (Days)", min_value=1, max_value=30, value=7)

    submitted = st.form_submit_button("Issue Invitation", type="primary")

    if submitted:
        try:
            invitation = create_invitation(
                inviter_email=user_email,
                organization_id=org_id,
                invitee_email=invite_email,
                role=invite_role,
                expiry_days=int(expiry_days),
            )
            st.success(
                f"✅ Invitation created for **{invitation.email}** ({invitation.role})."
            )
            st.code(f"Invitation Token: {invitation.token}\nExpiry: {invitation.expires_at}")
        except (OnboardingError, AuthorizationError, ValueError) as err:
            st.error(f"❌ Could not issue invitation: {err}")
        except Exception as exc:
            st.error(f"❌ Unexpected error: {exc}")

st.divider()

st.markdown("### Team Invitations")
invitations = get_invitations(org_id)

if not invitations:
    st.write("No invitations have been issued for this organization.")
else:
    for inv in invitations:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
            with c1:
                st.write(f"**{inv.email}**")
            with c2:
                st.write(f"`{inv.role}`")
            with c3:
                state_color = {
                    "INVITED": "orange",
                    "ACCEPTED": "green",
                    "EXPIRED": "gray",
                    "REVOKED": "red",
                }.get(inv.state, "blue")
                st.markdown(f":{state_color}[● {inv.state}]")
            with c4:
                st.caption(f"Expires: {inv.expires_at[:10] if inv.expires_at else 'N/A'}")
            with c5:
                if inv.state == "INVITED":
                    if st.button("Revoke", key=f"revoke_{inv.invitation_id}"):
                        try:
                            revoke_invitation(
                                invitation_id=inv.invitation_id,
                                revoker_email=user_email,
                                organization_id=org_id,
                            )
                            st.success(f"Revoked invitation for {inv.email}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to revoke: {e}")
            st.divider()
