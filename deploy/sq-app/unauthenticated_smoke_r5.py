"""SQ-APP r5 liveness-only launcher pending authorized real Auth."""
import json
import os
import sys

from cryptography.fernet import Fernet

sys.path.insert(0, "/opt/nexora-ops")
from runtime import secret_environment, storage_paths_available

SCOPE = "nexora-sqapp-r5-auth-pending-20261111:unauthenticated-only"


def main():
    env = secret_environment(os.environ)
    if env.get("NEXORA_SQAPP_SCOPE") != SCOPE:
        raise ValueError("scope")
    if env.get("ENVIRONMENT") != "production" or env.get("AUTH_MODE") != "supabase":
        raise ValueError("account mode")
    if any(
        env.get(name)
        for name in (
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
        )
    ):
        raise ValueError("Auth must be absent")
    if json.loads(env.get("API_USERS_JSON", "null")) != {}:
        raise ValueError("no accounts permitted")
    if any(
        env.get(name, "false").lower() != "false"
        for name in (
            "BACKGROUND_JOBS_ENABLED",
            "NEXORA_SCHEDULED_JOBS_ENABLED",
            "NEXORA_DEMO_MODE",
            "PUE_PILOT_DEV_MODE",
        )
    ):
        raise ValueError("execution disabled")
    for name in ("FERNET_KEY", "NEXORA_PROSPECT_DATA_KEY"):
        Fernet(env[name].encode())
    if env.get("NEXORA_SQAPP_ROLE") == "api" and len(env.get("JWT_SECRET", "")) < 32:
        raise ValueError("signing material")
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
    role = sys.argv[1]
    command = commands[role]
    print(
        "SQ_APP_AUTH_TARGET_UNAVAILABLE: r5 unauthenticated liveness only; "
        "protected readiness disabled",
        flush=True,
    )
    os.execvpe(command[0], command, env)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("SQ-APP r5 unauthenticated scope refused", file=sys.stderr)
        raise SystemExit(78) from None
