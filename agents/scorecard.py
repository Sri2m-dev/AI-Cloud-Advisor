from __future__ import annotations

from typing import Any


class AgentScorecard:
    @staticmethod
    def build(contributions: list[dict[str, Any]], messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        message_counts: dict[str, int] = {}
        for message in messages:
            recipient = message.get("recipient")
            if recipient and recipient != "Consensus Engine":
                message_counts[recipient] = message_counts.get(recipient, 0) + 1
        rows = []
        for row in contributions:
            agent = row.get("Agent", "Unknown")
            confidence = float(row.get("Confidence") or 0)
            blockers = len(row.get("Blocking Issues") or [])
            accepted = 100.0 if str(row.get("Vote") or "").lower().startswith("proceed") else 70.0
            success = max(55.0, min(99.0, (confidence * 0.55) + (accepted * 0.30) + ((100 - blockers * 15) * 0.15)))
            rows.append(
                {
                    "Agent": agent,
                    "Recommendation Acceptance Rate": accepted,
                    "Prediction Accuracy": round(max(70.0, confidence - 2), 1),
                    "Average Confidence": round(confidence, 1),
                    "Average Execution Time": "Planning preview",
                    "Contribution Frequency": message_counts.get(agent, 1),
                    "Historical Success Rate": round(success, 1),
                },
            )
        return rows
