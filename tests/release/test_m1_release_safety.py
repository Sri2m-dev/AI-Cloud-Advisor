"""M1 behavior tests; no SDK, network, SQL or database fixtures."""

import ast
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.audit_release_packaging import audit_context, audit_image, included
from services.release_readiness_service import ReleaseReadinessService

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    [
        "fernet.key",
        ".env.production",
        ".local/secret.py",
        "services/key.pem",
        "services/nested/.env",
        "services/credentials.json",
        "var/prospect_data/client.csv",
        "deploy/staging/NXR-CLOSE-016/evidence/G07/customer.zip",
        "backups/client.sql",
        "cloud_advisor.db",
        "node_modules/pkg/code.py",
        "docs/customer.pdf",
        "tests/security/test_secret.py",
        "data/customer.json",
        "archive/old.py",
        "services/customer.json",
        "services/nested/customer.csv",
    ],
)
def test_context_denies_private_and_unneeded_paths(path):
    assert not included(path, (ROOT / ".dockerignore").read_text())


@pytest.mark.parametrize(
    "path",
    [
        "app_main.py",
        "backend/main.py",
        "services/release_readiness_service.py",
        "backend/requirements.txt",
        "requirements.txt",
        "Dockerfile.frontend",
        "migrations/universal_evidence/0001_create_lifecycle_state.sql",
        "data/demo/nexora_global_retail.json",
        "deploy/nginx/nginx.conf",
    ],
)
def test_runtime_dependencies_remain_in_context(path):
    assert included(path, (ROOT / ".dockerignore").read_text())
    assert (ROOT / path).is_file()


def test_context_audit_does_not_read_excluded_secret(tmp_path):
    (tmp_path / ".dockerignore").write_text((ROOT / ".dockerignore").read_text())
    (tmp_path / "services").mkdir()
    (tmp_path / "services/release_readiness_service.py").write_text("value = 1")
    (tmp_path / "fernet.key").write_text("not-a-real-key")
    result = audit_context(tmp_path)
    assert [r["path"] for r in result["files"]] == ["services/release_readiness_service.py"]


@pytest.mark.parametrize(
    "path,content",
    [
        ("app/fernet.key", b"synthetic"),
        ("app/services/bad.py", b"-----BEGIN PRIVATE KEY-----"),
    ],
)
def test_image_audit_rejects_sensitive_paths_and_content(tmp_path, path, content):
    target = tmp_path / "image.tar"
    with tarfile.open(target, "w") as archive:
        entry = tarfile.TarInfo(path)
        entry.size = len(content)
        archive.addfile(entry, io.BytesIO(content))
    with pytest.raises(ValueError):
        audit_image(target)


def test_image_audit_accepts_application_source(tmp_path):
    target = tmp_path / "image.tar"
    with tarfile.open(target, "w") as archive:
        entry = tarfile.TarInfo("app/app_main.py")
        entry.size = 4
        archive.addfile(entry, io.BytesIO(b"pass"))
    assert audit_image(target)["application_entries"] == 1


@pytest.mark.parametrize("persist", [True, False])
def test_unverified_readiness_never_approves_or_scores(persist):
    service = ReleaseReadinessService("tenant-a")
    for method in (
        service.validate_release,
        service.validate_production_readiness,
        service.version_1_readiness_report,
    ):
        value = method(persist=persist)
        assert value["status"] == "NOT_VERIFIED"
        assert value["score"] is None
        serialized = json.dumps(value)
        assert '"Approved"' not in serialized
        assert '"Production Ready": "Yes"' not in serialized
        assert not any(isinstance(v, (int, float)) for v in value.values())
    assert service.validate_release()["kpis"]["Known Blockers"] is None


def extracted_method(file, cls, method, names):
    tree = ast.parse((ROOT / file).read_text(encoding="utf-8-sig"))
    definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    function = next(
        n for n in definition.body if isinstance(n, ast.FunctionDef) and n.name == method
    )
    function.decorator_list = []
    namespace = dict(names)
    exec(compile(ast.Module(body=[function], type_ignores=[]), file, "exec"), namespace)
    return namespace[method]


def test_platform_aggregate_propagates_unknown_without_fabricated_trend():
    names = {"Any": object, "READINESS_WEIGHTS": {"Release Readiness": 1.0}}
    calc = extracted_method(
        "services/platform_health_service.py",
        "PlatformHealthService",
        "calculate_readiness_score",
        names,
    )
    assert calc(None, {"Release Readiness": None})["classification"] == "NOT_VERIFIED"
    trend = extracted_method(
        "services/platform_health_service.py", "PlatformHealthService", "health_trend", names
    )
    assert trend(None, None) == {"24 hours": [], "7 days": [], "30 days": []}


def test_copilot_readiness_cannot_promote_stale_approved_payload():
    dummy = SimpleNamespace(_answer=lambda text, *a, **kw: text)
    answer = extracted_method(
        "services/ai_copilot_service.py",
        "AICopilotService",
        "_enterprise_readiness_answer",
        {"Any": object, "AICopilotService": dummy},
    )
    result = answer({"release_readiness": {"status": "Approved", "score": 100}})
    assert "NOT_VERIFIED" in result and "100" not in result


def test_readiness_page_does_not_display_hardcoded_approval():
    source = (ROOT / "pages/enterprise_readiness.py").read_text()
    assert "NOT_VERIFIED" in source
    assert "99.1%" not in source and "98.6%" not in source


def test_public_ingress_denies_api_metrics_and_docs_but_keeps_frontend():
    source = (ROOT / "deploy/nginx/nginx.conf").read_text()
    for route in ("/api/", "/metrics", "= /docs", "= /redoc", "= /openapi.json"):
        assert "location " + route + " { return 404; }" in source
    assert "proxy_pass http://streamlit_frontend" in source


def test_telemetry_requires_managed_password_file_and_loopback_ports():
    source = (ROOT / "docker-compose.telemetry.yml").read_text()
    assert "GF_SECURITY_ADMIN_PASSWORD=admin" not in source
    assert "GF_SECURITY_ADMIN_PASSWORD__FILE=/run/secrets/" in source
    assert "${GRAFANA_ADMIN_PASSWORD_FILE:?" in source
    for port in (9090, 3000, 3100):
        assert f'"127.0.0.1:{port}:{port}"' in source


def test_publication_has_no_automatic_or_webhook_bypass():
    source = (ROOT / ".github/workflows/cd.yml").read_text()
    assert "workflow_run:" not in source and "branches: [main]" not in source
    assert "DEPLOY_WEBHOOK" not in source and "curl -X POST" not in source
    assert "needs: verify" in source
    assert "ref: ${{ needs.verify.outputs.sha }}" in source
    assert "push: false" in source and "default: false" in source
    assert "environment: release-publication" in source
    assert "NEXORA_IMAGE_PUBLICATION_ENABLED == 'true'" in source
    assert "run.head_sha !== sha" in source and "run.conclusion !== 'success'" in source
    assert "workflow.path !== '.github/workflows/ci.yml'" in source
    assert "run.event !== 'push'" in source and "main.commit.sha !== sha" in source
    assert "repository_digests" in source and "release_sha" in source
    assert "audit_release_packaging.py --image-tar" in source


@pytest.mark.parametrize(
    "mutation", [None, "sha", "conclusion", "event", "branch", "repository", "workflow", "main"]
)
def test_exact_ci_provenance_verifier_rejects_mismatches(mutation):
    import os
    import shutil
    import subprocess
    import textwrap

    node = shutil.which("node")
    assert node, "Node is required to exercise the actual GitHub verifier offline"
    source = (ROOT / ".github/workflows/cd.yml").read_text()
    verifier = textwrap.dedent(
        source.split("          script: |\n", 1)[1].split("\n  package:", 1)[0]
    )
    run = {
        "workflow_id": 1,
        "head_sha": "a" * 40,
        "head_branch": "main",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": "owner/repo"},
        "head_repository": {"full_name": "owner/repo"},
    }
    workflow = {"path": ".github/workflows/ci.yml"}
    main = {"commit": {"sha": "a" * 40}}
    if mutation == "sha":
        run["head_sha"] = "b" * 40
    if mutation == "conclusion":
        run["conclusion"] = "failure"
    if mutation == "event":
        run["event"] = "pull_request"
    if mutation == "branch":
        run["head_branch"] = "feature"
    if mutation == "repository":
        run["head_repository"]["full_name"] = "fork/repo"
    if mutation == "workflow":
        workflow["path"] = ".github/workflows/other.yml"
    if mutation == "main":
        main["commit"]["sha"] = "b" * 40
    setup = "const run=" + json.dumps(run) + ";const workflow=" + json.dumps(workflow)
    setup += ";const main=" + json.dumps(main) + ";"
    setup += "const context={repo:{owner:'owner',repo:'repo'}};"
    setup += "const core={setOutput:(key,value)=>{}};"
    setup += (
        "const github={rest:{actions:{getWorkflowRun:async()=>({data:run}),"
        "getWorkflow:async()=>({data:workflow})},"
        "repos:{getBranch:async()=>({data:main})}}};"
    )
    code = (
        setup
        + "(async()=>{"
        + verifier
        + "})().then(()=>process.exit(0)).catch(()=>process.exit(9));"
    )
    result = subprocess.run(
        [node, "-e", code],
        env={**os.environ, "RELEASE_SHA": "a" * 40, "CI_RUN_ID": "123"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == (0 if mutation is None else 9), result.stderr
