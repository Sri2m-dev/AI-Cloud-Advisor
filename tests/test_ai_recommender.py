import pandas as pd

from ai_recommender import generate_recommendations


def test_generate_recommendations_includes_ec2_plan_for_ec2_top_service() -> None:
    service_cost = pd.DataFrame({"product_product_name": ["EC2", "S3", "RDS"]})

    recommendations = generate_recommendations(service_cost)

    assert "Implement EC2 Savings Plans" in recommendations
    assert "Enable S3 lifecycle policies" in recommendations


def test_generate_recommendations_skips_ec2_plan_when_not_top_service() -> None:
    service_cost = pd.DataFrame({"product_product_name": ["S3", "EC2", "RDS"]})

    recommendations = generate_recommendations(service_cost)

    assert "Implement EC2 Savings Plans" not in recommendations
