import streamlit as st
import pandas as pd
from typing import List, Dict

from shared.streamlit_compat import line_chart

def ForecastChart(data: List[Dict], x: str = "date", y: str = "forecast", title: str = "Forecast"):
    """
    Display a forecast line chart.
    """
    if not data:
        st.info("No forecast data available.")
        return
    df = pd.DataFrame(data)
    line_chart(df.set_index(x)[y])
    st.caption(title)

