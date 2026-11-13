"""Run a bounded offline regression in an allowlisted child environment."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

TESTS = [
    "tests/release/test_m1_release_safety.py",
    "tests/release/test_v11_release_hygiene.py",
    "tests/security/test_api_user_store.py",
    "tests/security/test_api_auth_tenant_authorization.py",
    "tests/security/test_token_store_revocation_contract.py",
    "tests/security/test_jwt_secret_policy.py",
    "tests/security/test_streamlit_auth_isolation.py",
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC"}
    }
    env.update(
        {
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHON_DOTENV_DISABLED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "ENVIRONMENT": "development",
            "NEXORA_COMPLIANCE_DB": "false",
            "P3_SUPABASE_RUN_INTEGRATION": "",
            "P3_SUPABASE_TEST_URL": "",
            "P3_SUPABASE_TEST_SERVICE_ROLE_KEY": "",
        }
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-p",
        "scripts.m1_offline_guard",
        "--tb=short",
        "--basetemp",
        str(args.output_dir / "pytest-temp"),
        "--junitxml",
        str(args.output_dir / "results.xml"),
        *TESTS,
    ]
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    (args.output_dir / "pytest.log").write_text(result.stdout + result.stderr)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    raise SystemExit(result.returncode)
