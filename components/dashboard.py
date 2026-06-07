"""Compatibility wrappers for the shared enterprise UI framework."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd

from shared.charts import render_chart as render_chart_container
from shared.components import kpi_cards
from shared.layout import render_page_header, render_section
from shared.tables import data_table, recommendation_table


def render_kpi_cards(metrics: Sequence[dict[str, Any]], columns: int | None = None) -> None:
    kpi_cards(metrics)


def render_recommendation_table(
    data: pd.DataFrame | Sequence[dict[str, Any]],
    columns: Sequence[str] | None = None,
    rename_columns: dict[str, str] | None = None,
    caption: str | None = None,
    empty_message: str = "No recommendations available.",
) -> None:
    recommendation_table(
        data,
        columns=columns,
        rename_columns=rename_columns,
        caption=caption,
        empty_message=empty_message,
    )


def render_data_table(
    data: pd.DataFrame | Sequence[dict[str, Any]],
    caption: str | None = None,
    empty_message: str = "No data available.",
) -> None:
    data_table(data, caption=caption, empty_message=empty_message)

