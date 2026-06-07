"""Reusable table compatibility wrappers."""

from shared.tables import data_table as _data_table


def data_table(data, use_container_width=True, **kwargs):
    _data_table(data, **kwargs)

