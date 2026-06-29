from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import streamlit as st


def render_notification_center(
    notifications: Sequence[dict[str, Any]] | None = None,
    *,
    max_items: int = 5,
) -> None:
    items = list(notifications or st.session_state.get("notifications", []))
    unread_count = sum(1 for item in items if not item.get("read"))

    menu = st.popover if hasattr(st, "popover") else st.expander
    with menu(f"Notifications ({unread_count})"):
        if not items:
            st.caption("No notifications")
            return
        for item in items[:max_items]:
            title = item.get("title") or item.get("message") or "Notification"
            detail = item.get("detail") or item.get("description")
            severity = item.get("severity") or item.get("status") or "info"
            st.write(f"**{title}**")
            if detail:
                st.caption(detail)
            st.caption(str(severity).title())
