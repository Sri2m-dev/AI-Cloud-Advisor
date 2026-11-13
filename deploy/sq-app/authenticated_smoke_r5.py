"""Fail-closed launcher for the isolated, synthetic Supabase Auth qualification."""
import json
import os
import sys

from cryptography.fernet import Fernet

sys.path.insert(0, "/opt/nexora-ops")
from runtime import secret_environment, storage_paths_available, validate

SCOPE = "nexora-sqapp-r5-auth-local-20261111:authenticated-local-only"
SUPABASE_URL = "https://auth-gateway:8443"


def main():
    env = secret_environment(os.environ)
    if env.get("NEXORA_SQAPP_SCOPE") != SCOPE:
        raise ValueError("deployment scope mismatch")
    if env.get("SUPABASE_URL") != SUPABASE_URL:
        raise ValueError("approved Auth target mismatch")
    if env.get("SUPABASE_API_AUTH_ENABLED") != "true":
        raise ValueError("Supabase API token verification must be enabled")
    if env.get("SUPABASE_JWT_ISSUER") != SUPABASE_URL:
        raise ValueError("Supabase issuer mismatch")
    if env.get("SUPABASE_JWT_AUDIENCE") != "authenticated":
        raise ValueError("Supabase audience mismatch")
    if not env.get("SUPABASE_ANON_KEY") or env.get("SUPABASE_KEY") != env.get("SUPABASE_ANON_KEY"):
        raise ValueError("the public anonymous key must be configured consistently")
    if env.get("SUPABASE_SERVICE_ROLE_KEY"):
        raise ValueError("privileged Supabase key is prohibited")
    if json.loads(env.get("API_USERS_JSON", "null")) != {}:
        raise ValueError("static API users are prohibited")
    for name in (
        "BACKGROUND_JOBS_ENABLED",
        "NEXORA_SCHEDULED_JOBS_ENABLED",
        "NEXORA_DEMO_MODE",
        "PUE_PILOT_DEV_MODE",
    ):
        if env.get(name, "false").lower() != "false":
            raise ValueError("background, demo, and protected execution must remain disabled")
    for name in ("FERNET_KEY", "NEXORA_PROSPECT_DATA_KEY"):
        Fernet(env[name].encode())
    role = sys.argv[1]
    validate(role, env)
    storage_paths_available(env)
    commands = {
        "frontend": [
            "streamlit",
            "run",
            "app_main.py",
            "--server.address=0.0.0.0",
            "--server.port=8501",
        ],
        "api": ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
    }
    command = commands[role]
    print("SQ-APP authenticated local staging; privileged execution remains disabled", flush=True)
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("SQ-APP authenticated staging startup refused", file=sys.stderr)
        raise SystemExit(78) from None
