"""Idempotently set ownership on isolated r5 storage directories."""
import os
from pathlib import Path


for path in (Path("/init") / name for name in ("application", "evidence", "prospect", "redis")):
    if not path.is_dir():
        raise SystemExit(f"Storage mount is missing: {path.name}")
    uid, gid = (999, 999) if path.name == "redis" else (10001, 10001)
    os.chown(path, uid, gid)
    os.chmod(path, 0o700)

print("Verified isolated r5 storage ownership")
