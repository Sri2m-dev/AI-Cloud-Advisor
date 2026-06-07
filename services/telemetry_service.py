from __future__ import annotations

from typing import Any


def summarize_workflow_telemetry(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    by_state: dict[str, int] = {}
    max_aging = 0
    for item in items:
        state = str(item.get("workflow_state") or "NEW")
        by_state[state] = by_state.get(state, 0) + 1
        max_aging = max(max_aging, int(item.get("aging_days") or 0))

    return {
        "total_items": total,
        "state_breakdown": by_state,
        "max_aging_days": max_aging,
    }

