"""Dry-run-first retention enforcement for encrypted recovery package files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def retention_candidates(
    directory: Path,
    *,
    older_than_days: int,
    keep_newest: int,
    now: float | None = None,
) -> list[Path]:
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("backup directory must be an existing, non-symlink directory")
    if older_than_days < 1 or keep_newest < 2:
        raise ValueError("retention requires at least one day and two protected backups")
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    backups = []
    for path in directory.iterdir():
        if path.suffix != ".fernet" or path.is_symlink() or not path.is_file():
            continue
        backups.append((path.stat().st_mtime, path.name, path))
    backups.sort(reverse=True)
    cutoff = now - older_than_days * 86400
    return [
        path
        for index, (modified, _, path) in enumerate(backups)
        if index >= keep_newest and modified < cutoff
    ]


def enforce_retention(
    directory: Path,
    *,
    older_than_days: int,
    keep_newest: int,
    apply: bool = False,
    now: float | None = None,
) -> dict[str, object]:
    candidates = retention_candidates(
        directory,
        older_than_days=older_than_days,
        keep_newest=keep_newest,
        now=now,
    )
    removed = []
    if apply:
        root = Path(directory).resolve()
        for path in candidates:
            if path.parent.resolve() != root or path.is_symlink() or path.suffix != ".fernet":
                raise ValueError("refusing to delete an out-of-scope backup artifact")
            path.unlink()
            removed.append(path.name)
    return {
        "mode": "APPLY" if apply else "DRY_RUN",
        "candidate_count": len(candidates),
        "candidate_names": [path.name for path in candidates],
        "deleted_names": removed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--older-than-days", type=int, required=True)
    parser.add_argument("--keep-newest", type=int, default=2)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = enforce_retention(
            args.directory,
            older_than_days=args.older_than_days,
            keep_newest=args.keep_newest,
            apply=args.apply,
        )
    except (OSError, ValueError) as error:
        print(f"Backup retention failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
