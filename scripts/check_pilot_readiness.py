"""Nexora external pilot readiness preflight.

This checker validates repository/local production prerequisites only.
It never validates real credentials or claims live external integration
certification.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_MANIFEST_SHA256 = (
    "4D9E0DE8EF1E19FE600605E8DC9FEA61C226442111E4A27F6F1724290EF190C0"
)

REQUIRED_FILES = (
    "docker-compose.production.yml",
    ".env.production.example",
    ".env.production.backend.example",
    "deploy/production/bootstrap-manifest.json",
    "docs/production/PILOT_RUNBOOK.md",
    "docs/production/PILOT_ACCEPTANCE_CHECKLIST.md",
)

REQUIRED_PUBLIC_TEMPLATE = (
    "ENVIRONMENT",
    "JWT_SECRET",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "NEXORA_UNIVERSAL_EVIDENCE_DB",
    "NEXORA_DEMO_MODE",
    "BACKGROUND_JOBS_ENABLED",
    "SCHEDULER_TZ",
)

REQUIRED_BACKEND_TEMPLATE = (
    "SUPABASE_SERVICE_ROLE_KEY",
)


def emit(key: str, value: object) -> None:
    print(f"{key}={value}")


def read_env_names(path: Path) -> set[str]:
    names: set[str] = set()

    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        name = line.split("=", 1)[0].strip()

        if name:
            names.add(name)

    return names


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest().upper()


def git_tracked() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    blocked: list[str] = []
    environment_required: list[str] = []

    emit("CHECK", "NEXORA_EXTERNAL_PILOT_READINESS")

    for relative in REQUIRED_FILES:
        exists = (ROOT / relative).is_file()
        emit(f"FILE_{relative.replace('/', '_')}", "PASS" if exists else "BLOCKED")

        if not exists:
            blocked.append(f"missing:{relative}")

    manifest = ROOT / "deploy/production/bootstrap-manifest.json"

    if manifest.is_file():
        actual_hash = sha256(manifest)
        emit("BOOTSTRAP_MANIFEST_SHA256", actual_hash)

        if actual_hash != EXPECTED_MANIFEST_SHA256:
            blocked.append("bootstrap_manifest_hash")

    public_template = ROOT / ".env.production.example"
    backend_template = ROOT / ".env.production.backend.example"

    if public_template.is_file():
        public_names = read_env_names(public_template)

        for name in REQUIRED_PUBLIC_TEMPLATE:
            present = name in public_names
            emit(f"PUBLIC_CONFIG_{name}", "PASS" if present else "BLOCKED")

            if not present:
                blocked.append(f"public_config:{name}")
    else:
        public_names = set()

    if backend_template.is_file():
        backend_names = read_env_names(backend_template)

        for name in REQUIRED_BACKEND_TEMPLATE:
            present = name in backend_names
            emit(f"BACKEND_CONFIG_{name}", "PASS" if present else "BLOCKED")

            if not present:
                blocked.append(f"backend_config:{name}")
    else:
        backend_names = set()

    if "SUPABASE_SERVICE_ROLE_KEY" in public_names:
        emit("FRONTEND_PRIVILEGED_CONFIG_BOUNDARY", "BLOCKED")
        blocked.append("service_role_in_public_template")
    else:
        emit("FRONTEND_PRIVILEGED_CONFIG_BOUNDARY", "PASS")

    tracked = git_tracked()

    tracked_runtime_env = [
        path
        for path in tracked
        if Path(path).name.startswith(".env")
        and not path.endswith(".example")
    ]

    tracked_private_keys = [
        path
        for path in tracked
        if Path(path).suffix.lower() in {".pem", ".p12", ".pfx", ".key"}
    ]

    emit("TRACKED_RUNTIME_ENV_COUNT", len(tracked_runtime_env))
    emit("TRACKED_PRIVATE_KEY_COUNT", len(tracked_private_keys))

    if tracked_runtime_env:
        blocked.append("tracked_runtime_env")

    if tracked_private_keys:
        blocked.append("tracked_private_key")

    runtime_env = ROOT / ".env.production"

    if runtime_env.is_file():
        runtime_names = read_env_names(runtime_env)
        emit("LOCAL_PRODUCTION_RUNTIME_CONFIG", "PRESENT")

        # Check safety-relevant non-secret settings without printing values.
        values: dict[str, str] = {}

        for raw in runtime_env.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

        if values.get("ENVIRONMENT", "").lower() == "production":
            emit("RUNTIME_ENVIRONMENT", "PASS")
        else:
            emit("RUNTIME_ENVIRONMENT", "BLOCKED")
            blocked.append("runtime_environment")

        if values.get("NEXORA_DEMO_MODE", "").lower() in {"false", "0", "no", "off"}:
            emit("RUNTIME_DEMO_MODE", "PASS")
        else:
            emit("RUNTIME_DEMO_MODE", "BLOCKED")
            blocked.append("runtime_demo_mode")

        if "JWT_SECRET" in runtime_names:
            emit("RUNTIME_JWT_SECRET", "PRESENT_NOT_PRINTED")
        else:
            emit("RUNTIME_JWT_SECRET", "BLOCKED")
            blocked.append("runtime_jwt_secret")
    else:
        emit("LOCAL_PRODUCTION_RUNTIME_CONFIG", "ENVIRONMENT_REQUIRED")
        environment_required.append("local_runtime_configuration")

    # External/live dependencies are intentionally not contacted.
    environment_required.extend(
        (
            "live_supabase_auth",
            "live_customer_connectors",
            "external_ai_provider_if_enabled",
            "external_notifications_if_enabled",
            "dns_tls_if_externally_exposed",
        )
    )

    for item in environment_required:
        emit(f"ENVIRONMENT_REQUIRED_{item.upper()}", "YES")

    emit("BLOCKER_COUNT", len(blocked))
    emit("ENVIRONMENT_REQUIRED_COUNT", len(environment_required))

    if blocked:
        for item in blocked:
            emit("BLOCKER", item)

        emit("RESULT", "BLOCKED")
        return 2

    emit("REPOSITORY_CERTIFIED", "PASS")
    emit("LOCAL_CONFIGURATION_PREFLIGHT", "PASS")
    emit("LIVE_EXTERNAL_INTEGRATIONS", "ENVIRONMENT_REQUIRED")
    emit("RESULT", "PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
