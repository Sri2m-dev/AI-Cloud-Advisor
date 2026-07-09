import streamlit as st
import pandas as pd
from typing import List, Dict

from shared.streamlit_compat import line_chart

def SpendChart(data: List[Dict], x: str = "date", y: str = "spend", title: str = "Cloud Spend Trend"):
    """
    Display a spend trend line chart.
    """
    if not data:
        st.info("No spend data available.")
        return
    df = pd.DataFrame(data)
    line_chart(df.set_index(x)[y])
    st.caption(title)

