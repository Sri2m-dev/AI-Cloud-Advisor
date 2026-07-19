from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.security import get_current_user, require_roles, tenant_guard


def _build_test_app() -> FastAPI:
    app = FastAPI()

    @app.get("/viewer")
    def viewer_endpoint(
        _user=Depends(get_current_user),
        _=Depends(require_roles(["viewer", "client_admin", "global_admin"])),
        tenant_id: str = Depends(tenant_guard),
    ):
        return {"tenant_id": tenant_id}

    @app.get("/admin")
    def admin_endpoint(
        _user=Depends(get_current_user),
        _=Depends(require_roles(["global_admin"])),
        tenant_id: str = Depends(tenant_guard),
    ):
        return {"tenant_id": tenant_id}

    return app


def test_tenant_isolation_allows_matching_header():
    app = _build_test_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "u1",
        "role": "viewer",
        "tenant_id": "tenant-a",
    }

    client = TestClient(app)
    response = client.get("/viewer", headers={"X-Tenant-Id": "tenant-a"})

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-a"


def test_tenant_isolation_blocks_mismatch():
    app = _build_test_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "u1",
        "role": "viewer",
        "tenant_id": "tenant-a",
    }

    client = TestClient(app)
    response = client.get("/viewer", headers={"X-Tenant-Id": "tenant-b"})

    assert response.status_code == 403


def test_tenant_isolation_denies_missing_identity_scope():
    app = _build_test_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "u1",
        "role": "viewer",
    }

    response = TestClient(app).get("/viewer")

    assert response.status_code == 400
    assert response.json()["detail"] == "organization_id is required"


def test_rbac_blocks_non_admin():
    app = _build_test_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "u2",
        "role": "viewer",
        "tenant_id": "tenant-a",
    }

    client = TestClient(app)
    response = client.get("/admin", headers={"X-Tenant-Id": "tenant-a"})

    assert response.status_code == 403


def test_rbac_allows_admin():
    app = _build_test_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "admin",
        "role": "global_admin",
        "tenant_id": "tenant-a",
    }

    client = TestClient(app)
    response = client.get("/admin", headers={"X-Tenant-Id": "tenant-a"})

    assert response.status_code == 200

