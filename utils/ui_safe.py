import streamlit as st
import pandas as pd


def safe_get(df, column, default=0):
    """
    Safely get dataframe column value.
    """
    try:
        if df is None or df.empty:
            return default

        if column not in df.columns:
            return default

        value = df.iloc[0][column]

        if pd.isna(value):
            return default

        return value

    except Exception:
        return default


def safe_metric(label, value, delta=None):
    """
    Render metric safely.
    """
    try:
        st.metric(label, value, delta)
    except Exception:
        st.metric(label, "N/A")


def executive_empty_state(
    title="Data Initializing",
    message="Cloud intelligence is currently synchronizing."
):
    """
    Enterprise-grade empty state.
    """

    st.info(f"""
### {title}

{message}

Please wait while the platform completes ingestion and model preparation.
""")


def safe_dataframe(df, message="No records available"):
    """
    Safely render dataframe.
    """

    try:
        if df is None or df.empty:
            st.warning(message)
        else:
            st.dataframe(df, use_container_width=True)

    except Exception:
        st.warning(message)


def safe_chart(chart_function, fallback_message="Visualization unavailable"):
    """
    Safely render charts.
    """

    try:
        chart_function()

    except Exception:
        st.warning(fallback_message)

