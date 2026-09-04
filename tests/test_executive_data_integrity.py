from services.enterprise_spend_certification_service import (
    EnterpriseSpendCertificationService,
    _numeric_total,
    _spend_value,
)
import pandas as pd


def test_missing_and_governed_zero_values_remain_distinguishable() -> None:
    assert _numeric_total(pd.DataFrame(), ["saas_cost"]) is None
    assert _numeric_total(pd.DataFrame({"saas_cost": [0.0]}), ["saas_cost"]) == 0.0
    assert _spend_value({}, "saas_spend", "saas_cost") is None
    assert _spend_value({"saas_cost": 0.0}, "saas_spend", "saas_cost") == 0.0


def test_enterprise_spend_summary_does_not_present_missing_sources_as_zero() -> None:
    metrics = {
        "total_spend": 0.0,
        "savings_opportunity": 0.0,
        "source_availability": {
            "spend": False,
            "recommendations": False,
        },
    }

    summary = EnterpriseSpendCertificationService._executive_summary(metrics, {}, {})

    assert "spend, allocation, and reconciliation are UNKNOWN" in summary
    assert "Optimization opportunity is UNKNOWN" in summary
    assert "$0" not in summary


def test_enterprise_spend_summary_preserves_available_recommendation_value() -> None:
    metrics = {
        "total_spend": 0.0,
        "savings_opportunity": 18_500.0,
        "source_availability": {
            "spend": False,
            "recommendations": True,
        },
    }

    summary = EnterpriseSpendCertificationService._executive_summary(metrics, {}, {})

    assert "spend, allocation, and reconciliation are UNKNOWN" in summary
    assert "Remaining optimization opportunity is $18.5K" in summary
