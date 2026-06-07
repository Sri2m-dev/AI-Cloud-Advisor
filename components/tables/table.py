import streamlit as st
import pandas as pd

def data_table(data: pd.DataFrame, pagination=True, sortable=True, searchable=True, exportable=True):
    # Basic table rendering
    st.dataframe(data, use_container_width=True)
    # TODO: Add pagination, sorting, search, export features

