"""Standard table rendering for enterprise dashboards."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd
import streamlit as st

from shared.streamlit_compat import dataframe
from shared.styles import apply_enterprise_styles


DEFAULT_TABLE_HEIGHT = 340
DEFAULT_RECOMMENDATION_TABLE_HEIGHT = 360


def _as_dataframe(data: pd.DataFrame | Sequence[dict[str, Any]] | Sequence[Any]) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    return pd.DataFrame(data)


def data_table(
    data: pd.DataFrame | Sequence[dict[str, Any]] | Sequence[Any],
    *,
    caption: str | None = None,
    empty_message: str = "No data available.",
    height: int = DEFAULT_TABLE_HEIGHT,
) -> None:
    """Render a fixed-height, scrollable enterprise data table."""
    apply_enterprise_styles()
    df = _as_dataframe(data)
    if df.empty:
        st.info(empty_message)
        return

    dataframe(df, hide_index=True, height=height)
    if caption:
        st.caption(caption)


def recommendation_table(
    data: pd.DataFrame | Sequence[dict[str, Any]] | Sequence[Any],
    columns: Sequence[str] | None = None,
    rename_columns: dict[str, str] | None = None,
    caption: str | None = None,
    empty_message: str = "No recommendations available.",
    height: int = DEFAULT_RECOMMENDATION_TABLE_HEIGHT,
) -> None:
    """Render recommendations with fixed-height scrolling for dense queues."""
    apply_enterprise_styles()
    df = _as_dataframe(data)
    if df.empty:
        st.info(empty_message)
        return

    if columns:
        visible_columns = [column for column in columns if column in df.columns]
        if visible_columns:
            df = df[visible_columns]

    if rename_columns:
        df = df.rename(columns=rename_columns)

    dataframe(df, hide_index=True, height=height)
    if caption:
        st.caption(caption)

