import pytest
from fastapi.testclient import TestClient

from api.v1.endpoints import app as compatibility_api
from auth.v1_route_policy import (
    allowed_page_specs,
    is_v1_page_allowed,
    route_catalogue,
)
from backend.main import app as production_api
from backend.main import startup_jobs
from components.sidebar_navigation import PAGE_PATHS, ROLE_PAGES


def test_route_catalogue_counts_and_blocks_deferred_and_supporting_pages():
    catalogue = route_catalogue()
    assert len(catalogue) == 113
    assert sum(row["scope"] == "SUPPORTED_CANDIDATE" for row in catalogue.values()) == 23
    assert sum(row["scope"] == "CONTROLLED_SUPPORTING" for row in catalogue.values()) == 8
    assert sum(row["scope"] == "DEFERRED_NOT_PUBLIC_V1" for row in catalogue.values()) == 82

    required = {
        "pages/login.py",
        "pages/logout.py",
        "pages/approval_center.py",
        "pages/reports.py",
    }
    candidates = {
        path
        for path, row in catalogue.items()
        if row["scope"] == "SUPPORTED_CANDIDATE"
    }
    assert candidates - {
        "pages/cost_intelligence.py",
        "pages/dependency_analysis.py",
        "pages/technology_digital_twin.py",
    } == {
        "pages/analyze_environment.py",
        "pages/application_inventory.py",
        "pages/approval_center.py",
        "pages/audit_timeline.py",
        "pages/ceo_workspace.py",
        "pages/cfo_workspace.py",
        "pages/cio_workspace.py",
        "pages/decision_intelligence.py",
        "pages/enterprise_ai_copilot.py",
        "pages/enterprise_registry.py",
        "pages/enterprise_spend.py",
        "pages/executive_command_center.py",
        "pages/finops_workspace.py",
        "pages/login.py",
        "pages/logout.py",
        "pages/operations_command_center.py",
        "pages/organization_administration.py",
        "pages/relationship_explorer.py",
        "pages/reports.py",
        "pages/welcome.py",
    }
    assert len(candidates - required - {
        "pages/cost_intelligence.py",
        "pages/dependency_analysis.py",
        "pages/technology_digital_twin.py",
    }) == 16

    all_candidate_pages = {
        row["navigation_labels"]: path
        for path, row in catalogue.items()
        if row["scope"] == "SUPPORTED_CANDIDATE"
    }
    all_labels = list(all_candidate_pages)
    all_paths = {**PAGE_PATHS, **all_candidate_pages}
    for path, row in catalogue.items():
        if row["scope"] != "SUPPORTED_CANDIDATE" or path not in required:
            assert not is_v1_page_allowed(
                path,
                "super_admin",
                page_paths=all_paths,
                role_pages={"super_admin": all_labels},
            )


def test_customer_workflow_pages_are_restricted_to_customer_roles():
    for page in (
        "pages/customer_workspace.py",
        "pages/approval_center.py",
        "pages/reports.py",
    ):
        assert is_v1_page_allowed(
            page,
            "finance",
            page_paths=PAGE_PATHS,
            role_pages=ROLE_PAGES,
        )
        assert not is_v1_page_allowed(
            page,
            "super_admin",
            page_paths=PAGE_PATHS,
            role_pages=ROLE_PAGES,
        )
        assert not is_v1_page_allowed(
            page,
            "technical",
            page_paths=PAGE_PATHS,
            role_pages=ROLE_PAGES,
        )


def test_registered_page_specs_exclude_non_v1_routes_and_keep_logout():
    specs = allowed_page_specs(
        "executive",
        page_paths=PAGE_PATHS,
        role_pages=ROLE_PAGES,
    )
    paths = {path for _, path in specs}
    assert "pages/customer_workspace.py" in paths
    assert "pages/approval_center.py" in paths
    assert "pages/reports.py" in paths
    assert "pages/logout.py" in paths
    assert "pages/risk_governance.py" not in paths
    assert "pages/business_services.py" not in paths
    assert "pages/cost_intelligence.py" not in paths
    assert "pages/dependency_analysis.py" not in paths
    assert "pages/technology_digital_twin.py" not in paths


def test_legacy_financial_and_graph_pages_are_denied_even_if_role_mapped():
    exclusions = (
        ("Cost Intelligence", "pages/cost_intelligence.py"),
        ("Dependency Analysis", "pages/dependency_analysis.py"),
        ("Technology Digital Twin", "pages/technology_digital_twin.py"),
    )
    for label, path in exclusions:
        assert not is_v1_page_allowed(
            path,
            "finance",
            page_paths={label: path},
            role_pages={"finance": [label]},
        )


def test_backend_entry_points_do_not_mount_deferred_routers():
    production_paths = {route.path for route in production_api.routes}
    compatibility_paths = {route.path for route in compatibility_api.routes}

    assert "/api/v1/approvals/list" in production_paths
    assert "/api/v1/approvals/list" in compatibility_paths
    for prefix in (
        "/api/v1/cost",
        "/api/v1/reports",
        "/api/v1/alerts",
        "/api/v1/recommendations",
        "/api/v1/governance",
        "/api/v1/finops",
        "/api/v1/saas",
    ):
        assert not any(
            path == prefix or path.startswith(prefix + "/")
            for path in production_paths
        )
        assert not any(
            path == prefix or path.startswith(prefix + "/")
            for path in compatibility_paths
        )


@pytest.mark.parametrize("app", [production_api, compatibility_api])
def test_direct_cost_api_access_is_unavailable(app):
    with TestClient(app) as client:
        assert client.get("/api/v1/cost").status_code == 404


def test_v1_api_fails_closed_when_legacy_background_jobs_are_enabled(monkeypatch):
    monkeypatch.setenv("BACKGROUND_JOBS_ENABLED", "true")
    with pytest.raises(RuntimeError, match="not supported by the V1 API route profile"):
        startup_jobs()
