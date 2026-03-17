from services.azure_optimization_engine import get_azure_optimization_recommendations
from services.gcp_optimization_engine import get_gcp_optimization_recommendations


REQUIRED_KEYS = {
    "category",
    "title",
    "description",
    "resource",
    "estimated_savings",
    "priority",
    "confidence_score",
    "rationale",
    "effort_level",
    "action_steps",
}


def _assert_recommendation_shape(items):
    assert items, "Expected at least one recommendation"
    for item in items:
        assert REQUIRED_KEYS.issubset(item.keys())
        assert isinstance(item["action_steps"], list)
        assert item["priority"] in {"low", "medium", "high"}
        assert isinstance(item["estimated_savings"], (int, float))


def test_azure_optimization_engine_payload_shape():
    _assert_recommendation_shape(get_azure_optimization_recommendations())


def test_gcp_optimization_engine_payload_shape():
    _assert_recommendation_shape(get_gcp_optimization_recommendations())
