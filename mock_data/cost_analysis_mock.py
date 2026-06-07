"""
mock_data/cost_analysis_mock.py

Stub data for views/cost_analysis.py sections that rely on
heuristics / hardcoded strings rather than live cloud telemetry.

Production replacement: root-cause classification should come from
an AI/ML model or AWS CloudTrail / Config change events stored in
Supabase `resource_change_events`. Confidence should be derived from
the model's own output.
"""

# ---------------------------------------------------------------------------
# Root-cause label map
# Maps service name → human-readable default root-cause string.
# Production replacement: AWS Config change events / CloudTrail lookup
#   filtered by resource type and correlated with cost spike timestamp.
# ---------------------------------------------------------------------------
ROOT_CAUSE_MAP: dict[str, str] = {
    "EC2": "Instance type change (t3.medium → m5.large)",
    "RDS": "Multi-AZ failover or read-replica addition",
    "Lambda": "Invocation-count spike or timeout increase",
    "S3": "Storage class transition or replication enabled",
    "EKS": "Node group scale-out event",
}

DEFAULT_ROOT_CAUSE = "Usage pattern change"

# ---------------------------------------------------------------------------
# Spike confidence
# Hardcoded 92 % confidence shown on spike recommendations.
# Production replacement: derive from statistical model (e.g. z-score
#   significance or anomaly detector's impact confidence field).
# ---------------------------------------------------------------------------
SPIKE_CONFIDENCE_PCT = 92

