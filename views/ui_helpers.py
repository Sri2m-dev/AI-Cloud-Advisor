"""
Shared UI utilities: empty states and toast notifications.

Usage
-----
from views.ui_helpers import render_empty_state, show_toast

# Empty state (returns True if the optional CTA button was clicked)
clicked = render_empty_state(
    icon="📊",
    title="No billing data yet",
    message="Connect a cloud account or load a demo to start exploring costs.",
    cta_label="Connect Account",
    cta_key="empty_connect_account",
)
if clicked:
    st.session_state["selected_page"] = "Cloud Accounts"
    st.rerun()

# Toast notification (transient — disappears automatically)
show_toast("Recommendation accepted.", icon="✅")
"""

import html as _html
import streamlit as st


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

_EMPTY_STATE_CSS = """
<style>
.es-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3.5rem 2rem 3rem;
    border: 1.5px dashed #d1d5db;
    border-radius: 14px;
    background: #fafafa;
    margin: 1.5rem 0;
}
.es-icon { font-size: 2.8rem; line-height: 1; margin-bottom: 0.8rem; }
.es-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #111827;
    margin: 0 0 0.45rem;
    text-align: center;
}
.es-message {
    font-size: 0.88rem;
    color: #6b7280;
    text-align: center;
    max-width: 440px;
    line-height: 1.55;
    margin: 0;
}
</style>
"""

_css_injected = False


def _inject_empty_state_css():
    global _css_injected
    if not _css_injected:
        st.markdown(_EMPTY_STATE_CSS, unsafe_allow_html=True)
        _css_injected = True


def render_empty_state(
    icon: str,
    title: str,
    message: str,
    cta_label: str | None = None,
    cta_key: str | None = None,
) -> bool:
    """
    Render a centred empty-state card with an icon, title, and message.

    Args:
        icon:       A single emoji or short text used as the visual centrepiece.
        title:      Bold headline (~5 words).
        message:    Supporting copy explaining what the user should do next.
        cta_label:  Optional call-to-action button label.
        cta_key:    Unique Streamlit key for the CTA button (required if cta_label is set).

    Returns:
        True if the CTA button was clicked this render cycle, False otherwise.
    """
    _inject_empty_state_css()

    safe_icon = _html.escape(str(icon))
    safe_title = _html.escape(str(title))
    safe_message = _html.escape(str(message))

    st.markdown(
        f"""
        <div class="es-card">
            <div class="es-icon">{safe_icon}</div>
            <p class="es-title">{safe_title}</p>
            <p class="es-message">{safe_message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if cta_label:
        # Centre the button with columns
        _, btn_col, _ = st.columns([2, 1.5, 2])
        with btn_col:
            return st.button(cta_label, key=cta_key or f"es_cta_{title[:20]}", type="primary", width="stretch")

    return False


# ---------------------------------------------------------------------------
# Toast notifications
# ---------------------------------------------------------------------------

def show_toast(message: str, icon: str = "✅") -> None:
    """
    Show a transient toast notification using st.toast().

    Args:
        message: Short notification text (≤80 chars recommended).
        icon:    Emoji to display alongside the message.
    """
    st.toast(message, icon=icon)
