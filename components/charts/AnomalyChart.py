import streamlit as st
import pandas as pd
from typing import List, Dict

def AnomalyChart(data: List[Dict], x: str = "date", y: str = "anomaly_score", title: str = "Anomaly Detection"):
    """
    Display an anomaly score chart.
    """
    if not data:
        st.info("No anomaly data available.")
        return
    df = pd.DataFrame(data)
    st.bar_chart(df.set_index(x)[y], use_container_width=True)
    st.caption(title)

