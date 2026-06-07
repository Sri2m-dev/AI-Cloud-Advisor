import streamlit as st
import pandas as pd
from typing import List, Dict

def ForecastChart(data: List[Dict], x: str = "date", y: str = "forecast", title: str = "Forecast"):
    """
    Display a forecast line chart.
    """
    if not data:
        st.info("No forecast data available.")
        return
    df = pd.DataFrame(data)
    st.line_chart(df.set_index(x)[y], use_container_width=True)
    st.caption(title)

