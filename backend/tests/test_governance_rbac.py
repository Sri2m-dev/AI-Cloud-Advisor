from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.security import get_current_user, require_role, tenant_guard


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/governance")
    def governance_endpoint(
        _user=Depends(get_current_user),
        _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "Auditor"])),
        _tenant=Depends(tenant_guard),
    ):
        return {"ok": True}

    @app.get("/recommendations-run")
    def rec_run_endpoint(
        _user=Depends(get_current_user),
        _=Depends(require_role(["SuperAdmin", "CustomerAdmin", "FinOpsManager"])),
        _tenant=Depends(tenant_guard),
    ):
        return {"ok": True}

    return app


def test_auditor_allowed_governance_only():
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "auditor",
        "role": "Auditor",
        "tenant_id": "t1",
    }
    client = TestClient(app)

    g = client.get("/governance", headers={"X-Tenant-Id": "t1"})
    r = client.get("/recommendations-run", headers={"X-Tenant-Id": "t1"})

    assert g.status_code == 200
    assert r.status_code == 403


def test_finopsmanager_not_governance_read():
    app = _app()
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "fm",
        "role": "FinOpsManager",
        "tenant_id": "t1",
    }
    client = TestClient(app)

    g = client.get("/governance", headers={"X-Tenant-Id": "t1"})
    assert g.status_code == 403

