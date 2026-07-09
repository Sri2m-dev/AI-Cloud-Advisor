import pandas as pd

from shared.streamlit_compat import dataframe

def data_table(data: pd.DataFrame, pagination=True, sortable=True, searchable=True, exportable=True):
    # Basic table rendering
    dataframe(data)
    # TODO: Add pagination, sorting, search, export features

