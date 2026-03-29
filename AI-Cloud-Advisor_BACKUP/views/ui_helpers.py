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


# ---------------------------------------------------------------------------
# Left-aligned table rendering (bypasses ag-grid)
# ---------------------------------------------------------------------------

def render_table_html(df, hide_index: bool = True) -> None:
    """
    Render a DataFrame as an HTML table with guaranteed left-alignment via inline styles.
    
    This bypasses Streamlit's ag-grid renderer and uses inline `style` attributes
    on every cell to ensure left-alignment cannot be overridden.
    
    Args:
        df: pandas DataFrame to render
        hide_index: If True, don't show the index column
    """
    import pandas as pd
    import re
    
    # Convert all numeric columns to formatted strings for display
    display_df = df.copy()
    for col in display_df.columns:
        if pd.api.types.is_numeric_dtype(display_df[col]):
            col_name = str(col).lower()
            # Currency columns
            if any(kw in col_name for kw in ("cost", "savings", "spend", "exposure", "amount", "price", "budget")):
                display_df[col] = display_df[col].apply(
                    lambda v: f"${v:,.0f}" if pd.notna(v) else ""
                )
            # Count columns
            elif any(kw in col_name for kw in ("records", "count")) and pd.api.types.is_integer_dtype(display_df[col]):
                display_df[col] = display_df[col].apply(
                    lambda v: f"{int(v):,}" if pd.notna(v) else ""
                )
            # Float columns
            elif pd.api.types.is_float_dtype(display_df[col]):
                display_df[col] = display_df[col].apply(
                    lambda v: f"{v:,.2f}" if pd.notna(v) else ""
                )
    
    # Generate base HTML table
    html_str = display_df.to_html(
        index=not hide_index,
        escape=False,
        border=0,
        float_format=lambda x: x
    )
    
    # Inject inline styles into every <th> and <td> for left-alignment
    # This is done via regex to inject style attributes
    html_str = re.sub(
        r'<th[^>]*>',
        lambda m: m.group(0).replace('>', ' style="text-align: left !important; padding: 10px; background: #f0f4f8; font-weight: 600; border: 1px solid #e5e7eb;">'),
        html_str
    )
    html_str = re.sub(
        r'<td[^>]*>',
        lambda m: m.group(0).replace('>', ' style="text-align: left !important; padding: 8px 10px; border: 1px solid #e5e7eb;">'),
        html_str
    )
    html_str = re.sub(
        r'<tr[^>]*>',
        lambda m: m.group(0) if 'even' in m.group(0) else m.group(0) + '<!-- alternating -->',
        html_str
    )
    
    # Add table-level styling
    html_table = f"""
    <style>
        .left-align-table {{ width: 100%; border-collapse: collapse; }}
        .left-align-table tr:nth-child(even) td {{ background: #f9fafb !important; }}
    </style>
    {html_str.replace('<table border="0"', '<table class="left-align-table" border="0"')}
    """
    
    st.markdown(html_table, unsafe_allow_html=True)
