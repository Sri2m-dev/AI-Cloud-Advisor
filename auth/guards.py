"""Compatibility shims for legacy imports.

This module provides small compatibility functions expected by older
modules that import from `auth.guards`. Keep these thin and delegate
to the single source-of-truth implementations.
"""

import streamlit as st

from shared import auth as _shared_auth
from auth.role_constants import normalize_role as _normalize_role


def require_auth():
	authenticated = bool(st.session_state.get("authenticated") or st.session_state.get("user"))
	if not authenticated:
		st.error("Please log in")
		st.stop()
	return st.session_state.get("user")


def require_role(allowed_roles):
	return _shared_auth.require_role(allowed_roles)


__all__ = ["require_auth", "require_role", "normalize_role"]


def normalize_role(role: object) -> str:
	return _normalize_role(role)

