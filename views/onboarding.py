"""
First-login onboarding wizard.

Guides new users through 4 quick steps:
  1. Welcome & workspace identity
  2. Monthly budget baseline + currency
  3. Connect your first cloud account
  4. Done — launch the dashboard

Calling render_onboarding_wizard() will show the wizard and return False while
the user is still working through it. Once the user clicks Finish, it marks
the onboarding as complete in the DB and returns True (app.py then reruns).
"""

import streamlit as st

from database.db import mark_onboarding_complete

TOTAL_STEPS = 4
CURRENCY_OPTIONS = ["USD ($)", "EUR (€)", "GBP (£)", "AUD (A$)", "CAD (C$)", "INR (₹)", "JPY (¥)", "SGD (S$)"]
TIMEZONE_OPTIONS = [
    "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
    "Europe/London", "Europe/Berlin", "Europe/Paris", "Asia/Kolkata",
    "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney",
]


def _step_progress(step: int):
    """Render a compact step-progress indicator."""
    labels = ["Welcome", "Budget", "Cloud Account", "Done"]
    cols = st.columns(len(labels))
    for i, (col, label) in enumerate(zip(cols, labels)):
        step_num = i + 1
        if step_num < step:
            col.markdown(
                f"<div style='text-align:center; color:#16a34a; font-weight:600; font-size:0.82rem;'>✓ {label}</div>",
                unsafe_allow_html=True,
            )
        elif step_num == step:
            col.markdown(
                f"<div style='text-align:center; color:#2563eb; font-weight:700; font-size:0.82rem;'>"
                f"● {label}</div>",
                unsafe_allow_html=True,
            )
        else:
            col.markdown(
                f"<div style='text-align:center; color:#9ca3af; font-size:0.82rem;'>○ {label}</div>",
                unsafe_allow_html=True,
            )
    st.markdown(
        f"<div style='margin: 0.4rem 0 1.2rem; background:#e5e7eb; border-radius:4px; height:4px;'>"
        f"<div style='width:{int((step - 1) / (TOTAL_STEPS - 1) * 100)}%; background:#2563eb; "
        f"border-radius:4px; height:4px;'></div></div>",
        unsafe_allow_html=True,
    )


def _step_1(username: str):
    """Welcome & workspace identity."""
    company = st.session_state.get("company") or "your organisation"
    st.markdown(
        f"## 👋 Welcome, **{username}**!\n\n"
        f"You're setting up the **{company}** workspace on Cloud Advisor. "
        "This takes about 2 minutes.",
    )
    st.markdown("---")

    st.markdown("**Preferred timezone**")
    tz = st.selectbox(
        "Timezone",
        TIMEZONE_OPTIONS,
        index=0,
        label_visibility="collapsed",
        key="onboard_tz",
    )
    st.caption("Used to align cost reports and alerts to your local business day.")

    st.markdown("**Your role at the company** *(optional)*")
    user_role_label = st.text_input(
        "Job title",
        placeholder="e.g. Head of Engineering, FinOps Lead, CTO",
        label_visibility="collapsed",
        key="onboard_role_label",
    )

    st.markdown("")
    if st.button("Next →", type="primary", key="onboard_next_1"):
        st.session_state["onboard_tz_value"] = tz
        st.session_state["onboard_role_label_value"] = user_role_label
        st.session_state["onboarding_step"] = 2
        st.rerun()


def _step_2():
    """Budget baseline + currency."""
    st.markdown("## 💰 Set your monthly cloud budget")
    st.markdown(
        "This baseline lets Cloud Advisor alert you when spend is trending over budget "
        "and gives the AI recommendations model a target to optimise toward."
    )
    st.markdown("---")

    col_cur, col_bud = st.columns([1, 2])
    with col_cur:
        st.markdown("**Currency**")
        currency = st.selectbox(
            "Currency",
            CURRENCY_OPTIONS,
            label_visibility="collapsed",
            key="onboard_currency",
        )
    with col_bud:
        st.markdown("**Monthly budget**")
        budget = st.number_input(
            "Monthly budget",
            min_value=0,
            max_value=10_000_000,
            value=10_000,
            step=1_000,
            label_visibility="collapsed",
            key="onboard_budget",
            help="You can change this at any time from the Dashboard.",
        )

    st.caption(
        f"Budget: **{currency.split()[0]} {budget:,}/month** — "
        "alerts will trigger at 85% and 100% of this limit."
    )

    st.markdown("")
    back_col, next_col = st.columns([1, 5])
    with back_col:
        if st.button("← Back", key="onboard_back_2"):
            st.session_state["onboarding_step"] = 1
            st.rerun()
    with next_col:
        if st.button("Next →", type="primary", key="onboard_next_2"):
            st.session_state["onboard_currency_value"] = currency
            st.session_state["onboard_budget_value"] = budget
            st.session_state["onboarding_step"] = 3
            st.rerun()


def _step_3():
    """Connect first cloud account (informational)."""
    st.markdown("## ☁️ Connect your first cloud account")
    st.markdown(
        "Cloud Advisor pulls cost data directly from your cloud providers using read-only "
        "credentials. No data leaves your account without your permission."
    )
    st.markdown("---")

    provider = st.radio(
        "Which provider do you want to connect first?",
        ["AWS", "Microsoft Azure", "Google Cloud Platform", "I'll do this later"],
        key="onboard_provider",
        horizontal=True,
    )

    if provider == "AWS":
        st.info(
            "**AWS setup** (takes ~5 minutes)\n\n"
            "1. In AWS IAM, create a read-only role with the `ReadOnlyAccess` managed policy.\n"
            "2. Generate an Access Key ID + Secret Access Key for that role.\n"
            "3. Paste them in **Cloud Accounts → Add Account** after finishing this wizard.\n\n"
            "**Tip:** Enable AWS Cost Explorer in your account if not already active — "
            "it can take 24 hours to populate data."
        )
    elif provider == "Microsoft Azure":
        st.info(
            "**Azure setup** (takes ~5 minutes)\n\n"
            "1. In Azure Active Directory, register an App registration.\n"
            "2. Assign it the **Cost Management Reader** role on the target subscription.\n"
            "3. Note the Tenant ID, Client ID, and Client Secret.\n"
            "4. Enter these in **Cloud Accounts → Add Account** after this wizard."
        )
    elif provider == "Google Cloud Platform":
        st.info(
            "**GCP setup** (takes ~5 minutes)\n\n"
            "1. Create a Service Account with the **Billing Account Viewer** role.\n"
            "2. Download the Service Account JSON key file.\n"
            "3. Upload it in **Cloud Accounts → Add Account** after this wizard.\n\n"
            "**Tip:** Enable the Cloud Billing API and BigQuery export for richer cost data."
        )
    else:
        st.info(
            "No problem — you can connect cloud accounts at any time from the **Cloud Accounts** page in the sidebar."
        )

    st.markdown("")
    back_col, next_col = st.columns([1, 5])
    with back_col:
        if st.button("← Back", key="onboard_back_3"):
            st.session_state["onboarding_step"] = 2
            st.rerun()
    with next_col:
        btn_label = "Next →" if provider != "I'll do this later" else "Skip & continue →"
        if st.button(btn_label, type="primary", key="onboard_next_3"):
            st.session_state["onboard_provider_value"] = provider
            st.session_state["onboarding_step"] = 4
            st.rerun()


def _step_4(username: str):
    """Done — summary and launch."""
    budget = st.session_state.get("onboard_budget_value", 10_000)
    currency = st.session_state.get("onboard_currency_value", "USD ($)")
    provider = st.session_state.get("onboard_provider_value", "—")
    tz = st.session_state.get("onboard_tz_value", "UTC")

    st.markdown("## 🎉 You're all set!")
    st.success(
        "Workspace configured successfully. Cloud Advisor is ready to start analysing your cloud costs."
    )

    st.markdown("**Your setup summary**")
    summary_col1, summary_col2 = st.columns(2)
    with summary_col1:
        st.markdown(f"- **Timezone:** {tz}")
        st.markdown(f"- **Monthly budget:** {currency.split()[0]} {budget:,}")
    with summary_col2:
        st.markdown(f"- **First cloud account:** {provider}")
        st.markdown(f"- **Account:** {username}")

    st.markdown("---")
    st.markdown(
        "**Your first steps after launch:**\n"
        "1. Head to **Cloud Accounts** to finish connecting your provider (if you skipped it).\n"
        "2. Open **Dashboard** to see your cost overview the moment data syncs.\n"
        "3. Visit **Optimization Insights** for AI-generated savings recommendations."
    )

    st.markdown("")
    if st.button("🚀 Launch Dashboard", type="primary", key="onboard_finish"):
        mark_onboarding_complete(username)
        # Clean up wizard state
        for key in [
            "onboarding_step", "onboard_tz_value", "onboard_role_label_value",
            "onboard_currency_value", "onboard_budget_value", "onboard_provider_value",
        ]:
            st.session_state.pop(key, None)
        st.rerun()


def render_onboarding_wizard():
    """
    Render the onboarding wizard. Must be called from app.py before the normal
    page routing block. Returns False while the wizard is still active so the
    caller knows to call st.stop() afterwards.
    """
    username = st.session_state.get("username", "")
    step = st.session_state.get("onboarding_step", 1)

    st.markdown(
        "<style>.block-container{max-width:780px !important;}</style>",
        unsafe_allow_html=True,
    )
    st.markdown("### Cloud Advisor — Getting Started")
    _step_progress(step)

    if step == 1:
        _step_1(username)
    elif step == 2:
        _step_2()
    elif step == 3:
        _step_3()
    elif step == 4:
        _step_4(username)

    return False
