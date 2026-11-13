"""Read-only operational configuration validation. Never contacts Docker or a DB."""
import argparse
import json
import os
from pathlib import Path
import re


IMAGE_NAMES = ("FRONTEND", "API", "WORKER", "BEAT", "NGINX", "REDIS", "PROMETHEUS", "ALERTMANAGER")


def validate_structure(config):
    services = config["services"]
    if not config["networks"]["application"].get("internal"):
        raise ValueError("internal service network required")
    for name, service in services.items():
        if name != "nginx" and service.get("ports"):
            raise ValueError("only ingress may publish ports")
        if service.get("build") or service.get("privileged"):
            raise ValueError("inspected images and unprivileged services required")
        for mount in service.get("volumes", []):
            if "docker.sock" in mount or mount.startswith("../../:/app"):
                raise ValueError("workspace/Docker socket mounts prohibited")
    if services["api"]["environment"]["BACKGROUND_JOBS_ENABLED"] != "false":
        raise ValueError("duplicate application scheduler prohibited")
    for name in ("frontend", "api", "worker", "beat"):
        if services[name]["environment"].get("NEXORA_PRODUCT_PROFILE") != "v1":
            raise ValueError("application services must use the V1 product profile")
    if services["beat"].get("profiles") != ["jobs"] or services["worker"].get("profiles") != ["jobs"]:
        raise ValueError("jobs must remain explicit opt-in")
    for name in ("worker", "beat"):
        environment = services[name]["environment"]
        if (
            environment.get("NEXORA_PRODUCT_PROFILE") != "v1"
            or environment.get("NEXORA_SCHEDULED_JOBS_ENABLED") != "false"
            or environment.get("NEXORA_ENABLED_PERIODIC_JOBS") != ""
        ):
            raise ValueError("legacy jobs must remain disabled in the V1 profile")
    if set(services["beat"]["secrets"]) != {"broker_url"}:
        raise ValueError("scheduler must not receive application encryption keys")
    if any(not value.startswith("127.0.0.1:") for value in services["nginx"]["ports"]):
        raise ValueError("unqualified ingress must remain loopback-only")
    return {"structure": "PASS", "services": len(services), "protected_execution_enabled": False}


def validate_inputs(environment, workspace):
    workspace = Path(workspace).resolve()
    for name in IMAGE_NAMES:
        image = environment.get("NEXORA_" + name + "_IMAGE", "")
        if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image):
            raise ValueError("inspected immutable image digests required")
    config = json.loads(Path(__file__).with_name("compose.yaml").read_text())
    required_files = {"NEXORA_PUBLIC_ENV_FILE"}
    for secret in config["secrets"].values():
        match = re.match(r"\$\{(NEXORA_\w+_FILE):", secret["file"])
        required_files.add(match[1])
    if any(not environment.get(name) for name in required_files):
        raise ValueError("all required managed file references must be supplied")
    public = Path(environment["NEXORA_PUBLIC_ENV_FILE"]).read_text()
    secret_names = {"JWT_SECRET","API_USERS_JSON","FERNET_KEY","NEXORA_PROSPECT_DATA_KEY","SUPABASE_SERVICE_ROLE_KEY",
                    "SUPABASE_KEY","SUPABASE_ANON_KEY","REDIS_URL","CELERY_BROKER_URL","CELERY_RESULT_BACKEND","PGPASSWORD","DATABASE_URL",
                    "SENTRY_DSN","OPENAI_API_KEY","STRIPE_SECRET_KEY","AWS_SECRET_ACCESS_KEY","AWS_SESSION_TOKEN","AZURE_CLIENT_SECRET"}
    for line in public.splitlines():
        name = line.strip().split("=",1)[0].removeprefix("export ").strip()
        if name in secret_names:
            raise ValueError("public configuration must not contain credential values")
    volume_names = []
    for volume in config["volumes"].values():
        match = re.match(r"\$\{(NEXORA_\w+_VOLUME):", volume["name"])
        value = environment.get(match[1], "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value):
            raise ValueError("explicit custodian-prepared persistent volume names required")
        volume_names.append(value)
    if len(set(volume_names)) != len(volume_names):
        raise ValueError("durable volumes must not alias each other")
    backup_status = Path(environment.get("NEXORA_BACKUP_STATUS_DIR", "")).resolve()
    if not backup_status.is_dir() or backup_status.is_relative_to(workspace):
        raise ValueError("dedicated external backup-status directory required")
    backup_root = Path(environment.get("NEXORA_BACKUP_ROOT", "")).resolve()
    if not backup_root.is_dir() or backup_root.is_relative_to(workspace):
        raise ValueError("dedicated external encrypted-backup directory required")
    for name, value in environment.items():
        if name.startswith("NEXORA_") and name.endswith("_FILE"):
            path = Path(value).resolve()
            if not path.is_file() or path.is_relative_to(workspace):
                raise ValueError("managed configuration/secret files must exist outside the repository")
    return {"inputs": "PASS", "runtime_qualified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-managed-inputs", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_structure(json.loads(Path(__file__).with_name("compose.yaml").read_text()))
        if args.validate_managed_inputs: result.update(validate_inputs(os.environ, Path.cwd()))
        print(json.dumps(result))
        return 0
    except Exception:
        print(json.dumps({"status": "OPERATIONAL_PREFLIGHT_FAILED"}))
        return 1


if __name__ == "__main__": raise SystemExit(main())
