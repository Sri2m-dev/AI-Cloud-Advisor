import pytest

from services import demo_tenant_service
from services.demo_tenant_service import DemoTenantError
from services.executive_workspace_composition_service import (
    ExecutiveWorkspaceCompositionService,
)


def test_demo_data_requires_explicit_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEXORA_DEMO_MODE", raising=False)

    with pytest.raises(DemoTenantError, match="not enabled"):
        demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")


def test_demo_data_rejects_production_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")

    with pytest.raises(DemoTenantError, match=r"demo-\*"):
        demo_tenant_service.load_demo_tenant("customer-production")


def test_demo_snapshot_is_labeled_and_decision_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    payload = demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")

    snapshot = ExecutiveWorkspaceCompositionService._demo_snapshot("ceo", payload)

    assert snapshot.synthetic is True
    assert all(metric.available for metric in snapshot.metrics)
    assert "$214.0M" in snapshot.metrics[0].value
    assert "NXR-INV-204" in snapshot.story.action
    assert "realized" in snapshot.story.outcome


def test_demo_classification_is_mandatory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXORA_DEMO_MODE", "true")
    original = demo_tenant_service.DEMO_DATA_PATH
    monkeypatch.setattr(demo_tenant_service, "DEMO_DATA_PATH", original)
    payload = demo_tenant_service.load_demo_tenant("demo-nexora-global-retail")

    assert payload["classification"] == "SYNTHETIC_DEMONSTRATION_DATA"
    assert payload["organization_id"].startswith("demo-")
