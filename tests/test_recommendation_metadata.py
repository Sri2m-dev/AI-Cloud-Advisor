from database import db as db_module


def test_save_recommendation_persists_rich_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db_module, "SQLITE_DB_PATH", str(tmp_path / "recommendations.db"))

    recommendation_id = db_module.save_recommendation(
        username="demo-user",
        category="forecast",
        title="Investigate forecast spike",
        description="Projected spend is above the recent baseline.",
        source="cost_forecast",
        resource="shared:forecast-spike",
        priority="high",
        estimated_savings=1500,
        confidence_score=0.88,
        rationale="The forecast is materially above the recent average and needs review.",
        effort_level="low",
        action_steps=[
            "Validate the services driving the increase.",
            "Confirm whether the change is expected demand or waste.",
        ],
    )

    recommendations = db_module.list_recommendations(username="demo-user", limit=10)

    assert recommendation_id is not None
    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation["confidence_score"] == 0.88
    assert recommendation["rationale"] == "The forecast is materially above the recent average and needs review."
    assert recommendation["effort_level"] == "low"
    assert recommendation["action_steps"] == [
        "Validate the services driving the increase.",
        "Confirm whether the change is expected demand or waste.",
    ]