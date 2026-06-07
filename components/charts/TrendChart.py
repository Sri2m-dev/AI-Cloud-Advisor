import streamlit as st
import pandas as pd
from typing import List, Dict

def TrendChart(data: List[Dict], x: str = "date", y: str = "value", title: str = "Trend"):
    """
    Display a generic trend line chart.
    """
    if not data:
        st.info("No trend data available.")
        return
    df = pd.DataFrame(data)
    st.line_chart(df.set_index(x)[y], use_container_width=True)
    st.caption(title)

