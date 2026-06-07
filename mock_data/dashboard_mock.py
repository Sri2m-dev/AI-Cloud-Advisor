"""
mock_data/dashboard_mock.py

Stub data for views/cto_dashboard.py sections shown while real
telemetry has not yet been ingested.

Production replacement: once `unified_cloud_costs` contains >= 7 days
of data, the onboarding preview chart is hidden and real data takes over
(see forecast_ready guard in cto_dashboard.py).
"""

# ---------------------------------------------------------------------------
# Onboarding trend-preview chart
# Shown in the empty state when no cloud cost rows exist yet.
# Values are normalised relative units (not dollars) — purely decorative.
# Production replacement: replaced automatically by forecast_ready=True path.
# ---------------------------------------------------------------------------
ONBOARDING_PREVIEW_VALS = [0.92, 1.05, 0.98, 1.10, 1.03, 1.12, 1.08]

