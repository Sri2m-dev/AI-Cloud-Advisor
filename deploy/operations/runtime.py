"""Mounted operational entrypoint. No network calls at import or secret logging."""
import json
import os
from pathlib import Path
import re
import sys

from cryptography.fernet import Fernet


def secret_environment(environment, read_text=None):
    env = dict(environment)
    reader = read_text or (lambda name: Path(name).read_text(encoding="utf-8"))
    names = ("JWT_SECRET", "API_USERS_JSON", "SUPABASE_KEY", "SUPABASE_ANON_KEY",
             "SUPABASE_SERVICE_ROLE_KEY", "FERNET_KEY", "NEXORA_PROSPECT_DATA_KEY", "REDIS_URL")
    for name in names:
        location = env.pop(name + "_FILE", None)
        if location:
            if env.get(name):
                raise ValueError("ambiguous managed secret configuration")
            value = reader(location).strip()
            if not value or len(value.encode()) > 131072:
                raise ValueError("managed secret missing or oversized")
            env[name] = value
    if env.get("REDIS_URL"):
        env["CELERY_BROKER_URL"] = env["REDIS_URL"]
        env["CELERY_RESULT_BACKEND"] = env["REDIS_URL"]
    return env


def validate(role, env):
    if env.get("ENVIRONMENT") != "production" or env.get("AUTH_MODE", "").lower() != "supabase":
        raise ValueError("production Supabase account mode required")
    if env.get("NEXORA_PRODUCT_PROFILE", "").strip().lower() != "v1":
        raise ValueError("the NEXORA V1 product profile is required")
    if role in {"worker", "beat"}:
        raise ValueError("legacy Celery jobs are excluded from the V1 profile")
    if env.get("BACKGROUND_JOBS_ENABLED", "false").lower() != "false":
        raise ValueError("API APScheduler must remain disabled")
    if env.get("NEXORA_JOB_SCHEDULER") != "celery":
        raise ValueError("one authoritative application scheduler required")
    if role in {"frontend", "api", "worker"}:
        for name in ("FERNET_KEY", "NEXORA_PROSPECT_DATA_KEY"):
            if not env.get(name):
                raise ValueError("stable managed encryption keys required")
            Fernet(env[name].encode("ascii"))
        for name in ("NEXORA_APPLICATION_DB", "NEXORA_UNIVERSAL_EVIDENCE_DB", "NEXORA_PROSPECT_DATA_ROOT"):
            if not env.get(name, "").startswith("/var/lib/nexora/"):
                raise ValueError("durable absolute data paths required")
        if not env.get("SUPABASE_URL", "").startswith("https://"):
            raise ValueError("approved HTTPS Auth endpoint required")
    if role == "api":
        if len(env.get("JWT_SECRET", "")) < 32 or not isinstance(json.loads(env.get("API_USERS_JSON", "null")), dict):
            raise ValueError("managed API account and signing configuration required")
    if role in {"worker", "beat"} and env.get("NEXORA_SCHEDULED_JOBS_ENABLED") != "true":
        raise ValueError("scheduled jobs remain disabled pending qualification")


def render_edge(hostname, template, destination):
    if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?", hostname or ""):
        raise ValueError("valid canonical ingress hostname required")
    content = template.replace("@@PUBLIC_HOST@@", hostname)
    Path(destination).write_text(content, encoding="utf-8")


def storage_paths_available(env):
    for name in ("NEXORA_APPLICATION_DB", "NEXORA_UNIVERSAL_EVIDENCE_DB", "NEXORA_PROSPECT_DATA_ROOT"):
        path = Path(env[name]) if name.endswith("ROOT") else Path(env[name]).parent
        if not path.is_dir() or not os.access(path, os.R_OK | os.W_OK | os.X_OK):
            raise ValueError("durable storage unavailable; no local fallback")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["health-worker"]:
        import socket
        os.environ.update(secret_environment(os.environ))
        from backend.celery_app import celery_app
        responses = celery_app.control.inspect(timeout=3, destination=["celery@" + socket.gethostname()]).ping()
        return 0 if responses and all(value.get("ok") == "pong" for value in responses.values()) else 1
    if args == ["health-beat"]:
        pid = int(Path("/var/lib/nexora/scheduler/beat.pid").read_text())
        if pid <= 0: return 1
        os.kill(pid, 0)
        return 0
    if args == ["render-edge"]:
        render_edge(os.environ.get("NEXORA_PUBLIC_HOST"),
                    Path("/opt/nexora-ops/nginx.conf.template").read_text(), "/etc/nexora-edge/nginx.conf")
        return 0
    if len(args) < 3 or args[1] != "--":
        raise ValueError("role and explicit foreground command required")
    role = args[0]
    env = secret_environment(os.environ)
    validate(role, env)
    if role in {"frontend", "api", "worker"}: storage_paths_available(env)
    if role == "beat":
        import fcntl
        # Shared single-host volume, inherited across foreground exec. No detached
        # beat, remote filesystem or multi-host singleton guarantee is claimed.
        lock = os.open("/var/lib/nexora/scheduler/beat.lock", os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.set_inheritable(lock, True)
    os.execvpe(args[2], args[2:], env)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("Operational startup refused; check managed configuration and qualification", file=sys.stderr)
        raise SystemExit(78) from None
