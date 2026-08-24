from pathlib import Path

from components.sidebar_navigation import DEFAULT_ROLE_PAGE, PAGE_PATHS
from scripts.smoke_role_routes import route_for_role

ROOT = Path(__file__).parents[1]


def test_frontend_container_uses_certified_entry_point() -> None:
    dockerfile = (ROOT / "Dockerfile.frontend").read_text(encoding="utf-8")
    assert '"app_main.py"' in dockerfile
    assert '"app.py"' not in dockerfile


def test_container_context_excludes_local_databases_and_secrets() -> None:
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "*.db" in dockerignore
    assert ".env" in dockerignore


def test_connector_runtime_dependencies_are_packaged() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for dependency in (
        "boto3==",
        "azure-identity==",
        "azure-mgmt-resource==",
        "azure-mgmt-costmanagement==",
    ):
        assert dependency in requirements

    dockerfiles = (
        "Dockerfile.frontend",
        "Dockerfile.api",
        "Dockerfile.worker",
        "Dockerfile.beat",
    )
    for name in dockerfiles:
        dockerfile = (ROOT / name).read_text(encoding="utf-8")
        assert "requirements.txt" in dockerfile
        assert "requirements-prod.txt" in dockerfile


def test_deployment_manifest_has_application_health_checks() -> None:
    compose = (ROOT / "docker-compose.deploy.yml").read_text(encoding="utf-8")
    assert "http://localhost:8501/_stcore/health" in compose
    assert "http://localhost:8000/health" in compose


def test_every_default_role_route_exists() -> None:
    for role, path in DEFAULT_ROLE_PAGE.items():
        assert path in PAGE_PATHS.values(), role
        assert (ROOT / path).is_file(), role


def test_smoke_routing_matches_application_defaults() -> None:
    assert route_for_role("ceo") == DEFAULT_ROLE_PAGE["executive"]
    assert route_for_role("cfo") == DEFAULT_ROLE_PAGE["finance"]
    assert route_for_role("customer_admin") == DEFAULT_ROLE_PAGE["client_admin"]
    assert route_for_role("unknown") == "pages/login.py"
    assert route_for_role("ceo", authenticated=False) == "pages/login.py"
