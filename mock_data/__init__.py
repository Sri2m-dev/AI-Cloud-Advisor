"""
mock_data — Isolated stubs for demo / pre-ingestion states.

These values are NEVER used once live telemetry is available.
Each module documents which production API / Supabase table will
replace the stub and how to wire it up.

Usage pattern in views:
    from mock_data.optimization_mock import COMMITMENT_MOCK
    monthly_commitment = live_value if live_value else COMMITMENT_MOCK["monthly_commitment"]
"""

