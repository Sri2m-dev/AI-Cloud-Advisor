"""Compatibility shim for session helpers used by older modules.

This small module provides a stable API surface expected by legacy imports
(`auth.session`) while delegating to the shared Streamlit-backed session
implementation in `shared.session`.

It is intentionally minimal and safe for local/demo runs.
"""

from typing import Any
import streamlit as st


def init_session() -> None:
    """Initialize common session keys if missing."""
    defaults = {
        "authenticated": False,
        "user": None,
        "role": None,
        "organization_id": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get(key: str, default: Any = None) -> Any:
    return st.session_state.get(key, default)


def set(key: str, value: Any) -> None:
    st.session_state[key] = value


def clear() -> None:
    for k in list(st.session_state.keys()):
        del st.session_state[k]

