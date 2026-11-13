"""Sanitized offline regression; no database qualification execution mode."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from scripts.prepare_m2c_qualification import prepare

REPORT = Path("docs/release/nexora-v1-m2c-2026-11-08")
TESTS = [
    "tests/release/test_m1_release_safety.py", "tests/release/test_v11_release_hygiene.py",
    "tests/security/test_api_user_store.py", "tests/security/test_api_auth_tenant_authorization.py",
    "tests/security/test_token_store_revocation_contract.py", "tests/security/test_jwt_secret_policy.py",
    "tests/security/test_streamlit_auth_isolation.py", "tests/security/test_production_tenant_provisioning.py",
    "tests/auth/test_tenant_authorization_foundation.py", "tests/services/test_v1_approval_authority.py",
    "tests/services/test_approval_service.py",
    "tests/database_integrity/test_g08_offline.py", "tests/owner_authorization", "tests/g08_integration",
]
CHANGED = ["auth/authenticated_tenant.py", "backend/routes/auth.py", "api/v1/approvals.py",
           "services/v1_approval_authority.py", "scripts/provision_production_tenant.py",
           "repositories/v1_approval_repository.py", "repositories/g08_transaction.py",
           "scripts/prepare_m2c_qualification.py", "scripts/run_m2c_verification.py"]
CHANGED += ["services/approval_service.py", "tests/services/test_approval_service.py", "backend/middleware/tenant_isolation.py"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=REPORT / "offline")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prepare(REPORT / "qualification")
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC"}}
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHON_DOTENV_DISABLED="1",
               PYTHONDONTWRITEBYTECODE="1", ENVIRONMENT="development", NEXORA_COMPLIANCE_DB="false")
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "scripts.m1_offline_guard",
               "--tb=short", "--basetemp", str(args.output_dir / "pytest-temp"),
               "--junitxml", str(args.output_dir / "results.xml"), *TESTS]
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    (args.output_dir / "pytest.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    print(result.stdout)
    if result.stderr: print(result.stderr)
    baseline = json.loads((REPORT / "preservation-baseline.json").read_text())["sha256"]
    altered = [p for p, digest in baseline.items() if not Path(p).is_file()
               or hashlib.sha256(Path(p).read_bytes()).hexdigest() != digest]
    sources = [Path(p) for p in CHANGED] + sorted(Path("tests/g08_integration").glob("*.py"))
    sources += [Path("database/contracts/g08_m2c/qualification/unknown_commit_probe.py")]
    for p in sources: ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    checks = {"preserved_files": len(baseline), "unexpected_changes": altered,
              "python_sources_parsed": len(sources), "postgresql_executed": False,
              "sql_parser_executed": False, "test_command": command}
    (args.output_dir / "checks.json").write_text(json.dumps(checks, indent=2)+"\n")
    files = sources + sorted(Path("database/contracts/g08_m2c").rglob("*.sql")) + sorted(REPORT.glob("*.md"))
    (REPORT / "artifact-manifest.json").write_text(json.dumps({"sha256": {
        p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},indent=2)+"\n")
    print(json.dumps({k: v for k, v in checks.items() if k != "test_command"}))
    return result.returncode or bool(altered)


if __name__ == "__main__":
    raise SystemExit(main())
