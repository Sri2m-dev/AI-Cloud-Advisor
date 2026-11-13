"""Private operational probes/exporter. No clients, connections or server at import."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import threading
import time
from urllib.request import urlopen


DATA_PATHS = {"application": "/var/lib/nexora/application", "evidence": "/var/lib/nexora/evidence",
              "prospect": "/var/lib/nexora/prospect", "backup": "/var/lib/nexora/backup"}


def http_probe(url):
    with urlopen(url, timeout=3) as response:
        return response.status == 200


def postgres_probe(config):
    if config.get("sslmode") != "verify-full" or config.get("connect_timeout", 3) > 5:
        raise ValueError("verified TLS and bounded PostgreSQL connection required")
    import psycopg2
    connection = psycopg2.connect(**(config | {"connect_timeout": 3, "options": "-c default_transaction_read_only=on -c statement_timeout=3000"}))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    finally:
        connection.close()


def collect(*, env=None, now=None, probe=http_probe, disk_usage=shutil.disk_usage, pg_probe=postgres_probe, redis_probe=None):
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    components = {}
    for name, url in {"api": "http://api:8000/health", "frontend": "http://frontend:8501/_stcore/health"}.items():
        try: components[name] = probe(url) is True
        except Exception: components[name] = False
    # External targets are never probed merely because credentials exist. This is
    # an operational switch requiring separate target permission, not identity assurance.
    components.update(postgres=False, auth=False, redis=False)
    if env.get("NEXORA_EXTERNAL_PROBES_ENABLED") == "true":
        try:
            config = json.loads(Path("/run/secrets/pg_monitor").read_text())
            components["postgres"] = pg_probe(config) is True
        except Exception: pass
        try:
            url = env.get("SUPABASE_URL", "")
            if not url.startswith("https://"): raise ValueError("HTTPS Auth endpoint required")
            components["auth"] = probe(url.rstrip("/") + "/auth/v1/health") is True
        except Exception: pass
    try:
        if redis_probe is None:
            import redis
            broker = Path(env["REDIS_URL_FILE"]).read_text().strip()
            client = redis.Redis.from_url(broker, socket_connect_timeout=3, socket_timeout=3)
            try: components["redis"] = client.ping() is True
            finally: client.close()
        else:
            components["redis"] = redis_probe() is True
    except Exception: pass
    storage = {}
    for name, path in DATA_PATHS.items():
        try:
            stats = disk_usage(path)
            storage[name] = {"free_ratio": stats.free / stats.total, "available_bytes": stats.free}
        except Exception:
            storage[name] = {"free_ratio": 0, "available_bytes": 0}
    try:
        backup = json.loads(Path("/var/lib/nexora/backup-status/status.json").read_text())
    except Exception:
        backup = {}
    backup_ok = backup.get("last_attempt_success") is True and 0 <= now - backup.get("last_success", 0) <= 90000 and backup.get("last_success", 0) > 0
    return {"observed_at": now, "components": components, "storage": storage,
            "infrastructure_ready": all(components.values()) and all(item["free_ratio"] > 0.10 for item in storage.values()) and backup_ok,
            "protected_execution_enabled": False,
            "backup_last_success": backup.get("last_success", 0),
            "backup_last_attempt_success": backup.get("last_attempt_success", False)}


def metrics(status):
    lines = []
    for name, value in status["components"].items():
        lines.append(f'nexora_dependency_up{{component="{name}"}} {int(value)}')
    for name, item in status["storage"].items():
        lines.append(f'nexora_storage_free_ratio{{volume="{name}"}} {item["free_ratio"]}')
        lines.append(f'nexora_storage_available_bytes{{volume="{name}"}} {item["available_bytes"]}')
    lines += [f'nexora_backup_last_success_timestamp {status["backup_last_success"]}',
              f'nexora_backup_last_attempt_success {int(status["backup_last_attempt_success"])}',
              f'nexora_infrastructure_ready {int(status["infrastructure_ready"])}',
              'nexora_protected_execution_enabled 0',
              f'nexora_probe_observed_timestamp {status["observed_at"]}']
    return "\n".join(lines) + "\n"


def main():
    state = {"status": None}
    def sample():
        while True:
            status = collect()
            # Atomic file handoff. File is operational status, never authorization.
            temporary = Path("/var/lib/nexora/status/readiness.tmp")
            temporary.write_text(json.dumps(status))
            temporary.replace("/var/lib/nexora/status/readiness.json")
            state["status"] = status
            time.sleep(30)
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status = state["status"]
            if self.path == "/health": code, body = 200, "alive"
            elif self.path == "/metrics" and status is not None: code, body = 200, metrics(status)
            elif self.path == "/ready": code, body = (200 if status and status["infrastructure_ready"] else 503), "infrastructure only"
            else: code, body = 404, "unavailable"
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(body.encode())
        def log_message(self, *args): pass
    threading.Thread(target=sample, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 9108), Handler).serve_forever()


if __name__ == "__main__": main()
