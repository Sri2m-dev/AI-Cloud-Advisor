from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any


class ConsensusEngine:
    @staticmethod
    def reach_consensus(contributions: list[dict[str, Any]]) -> dict[str, Any]:
        votes = [row.get("Vote") or row.get("Recommendation") or "Proceed" for row in contributions]
        vote_counts = Counter(votes)
        blockers = [
            issue
            for row in contributions
            for issue in row.get("Blocking Issues", [])
            if issue
        ]
        confidence_values = [float(row.get("Confidence") or 0) for row in contributions]
        agreements = [row for row in contributions if str(row.get("Vote") or "").lower().startswith("proceed")]
        disagreements = [
            row
            for row in contributions
            if row.get("Blocking Issues") or "await" in str(row.get("Recommendation") or "").lower()
        ]
        if any("CAB" in issue for issue in blockers):
            recommendation = "Proceed after CAB approval."
        elif blockers:
            recommendation = "Proceed after blocking issues are resolved."
        elif any("modifications" in str(vote).lower() for vote in votes):
            recommendation = "Proceed during scheduled maintenance window."
        else:
            recommendation = "Proceed."
        confidence = round(mean(confidence_values), 1) if confidence_values else 0.0
        reason = ConsensusEngine._reason(recommendation, contributions, blockers)
        return {
            "Enterprise Recommendation": recommendation,
            "Confidence": confidence,
            "Reason": reason,
            "Consensus State": "Consensus Reached" if contributions else "Awaiting Contributions",
            "Votes": [{"Vote": key, "Count": value} for key, value in vote_counts.items()],
            "Agreements": len(agreements),
            "Disagreements": len(disagreements),
            "Blocking Issues": blockers,
        }

    @staticmethod
    def _reason(recommendation: str, contributions: list[dict[str, Any]], blockers: list[str]) -> str:
        agents = ", ".join(row.get("Agent", "Agent") for row in contributions)
        if blockers:
            return f"{agents} support the plan once governance and blocking issues are satisfied."
        if "maintenance" in recommendation.lower():
            return f"{agents} support execution with operational safeguards and maintenance controls."
        return f"{agents} support the plan with no unresolved blocking issues."
