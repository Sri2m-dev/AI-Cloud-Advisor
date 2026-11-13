"""Inspect the allowlisted context or an exported image, never run the image.

No secret values are printed. Excluded directories are pruned without reading
contents. This matcher supports the explicit patterns used in .dockerignore;
Docker-backed inspection remains necessary to qualify Docker's actual context.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4096)
def pattern_regex(pattern: str) -> re.Pattern:
    pattern = pattern.strip("/")
    result = ""
    index = 0
    while index < len(pattern):
        if pattern[index : index + 3] == "**/":
            result += "(?:.*/)?"
            index += 3
        elif pattern[index : index + 2] == "**":
            result += ".*"
            index += 2
        elif pattern[index] == "*":
            result += "[^/]*"
            index += 1
        else:
            result += re.escape(pattern[index])
            index += 1
    return re.compile("^" + result + "$", re.IGNORECASE)


def included(path: str, rules: str) -> bool:
    allowed = True
    for line in rules.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if pattern_regex(line[1:] if negated else line).fullmatch(path.strip("/")):
            allowed = negated
    return allowed


def sensitive_path(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name.lower()
    return (
        any(
            p.lower()
            in {
                ".local",
                ".git",
                ".aws",
                ".docker",
                "backups",
                "archive",
                "restoration",
                "prospect_data",
            }
            for p in parts
        )
        or name.startswith(".env")
        or name == "secrets.toml"
        or name.endswith((".key", ".pem", ".p12", ".pfx", ".db", ".log"))
        or ".sqlite" in name
        or "credentials" in name
    )


def check_content(data: bytes) -> None:
    patterns = (
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"AKIA[0-9A-Z]{16}",
        rb"sk-proj-[A-Za-z0-9_-]{40,}",
    )
    if any(re.search(pattern, data) for pattern in patterns):
        raise ValueError("Credential-like content in application payload (value suppressed)")


def audit_context(root: Path) -> dict:
    rules = (root / ".dockerignore").read_text()
    records = []

    def visit(directory: Path):
        for child in sorted(directory.iterdir()):
            relative = child.relative_to(root).as_posix()
            allowed = included(relative, rules)
            prefixes = [
                line[1:].split("*")[0].rstrip("/")
                for line in rules.splitlines()
                if line.startswith("!")
            ]
            descend = any(
                relative == base
                or relative.startswith(base + "/")
                or base.startswith(relative + "/")
                for base in prefixes
                if base
            )
            if not allowed and not descend:
                continue
            if sensitive_path(relative):
                if not allowed:
                    continue
                raise ValueError("Sensitive path allowed by build policy")
            if child.is_symlink():
                raise ValueError("Build context contains a symlink")
            if child.is_dir():
                visit(child)
            elif child.is_file() and allowed:
                if sensitive_path(relative):
                    raise ValueError("Sensitive path allowed by build policy")
                data = child.read_bytes()
                check_content(data)
                records.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest()})

    visit(root)
    return {
        "kind": "modeled_allowlisted_context",
        "files": records,
        "file_count": len(records),
        "sensitive_paths": 0,
        "docker_engine_verified": False,
    }


def audit_image(archive: Path, prefix: str = "app/") -> dict:
    checked = 0
    with tarfile.open(archive, "r|*") as image:
        for member in image:
            path = member.name.removeprefix("./")
            if not path.startswith(prefix):
                continue
            if member.issym() or member.islnk() or sensitive_path(path):
                raise ValueError("Sensitive or linked application path in image")
            if member.isfile():
                payload = image.extractfile(member)
                check_content(payload.read() if payload else b"")
            checked += 1
    if not checked:
        raise ValueError("No application files found in exported image")
    return {
        "kind": "exported_image_path_inspection",
        "application_entries": checked,
        "sensitive_paths": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--image-tar", type=Path)
    parser.add_argument("--prefix", default="app/")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (
        audit_image(args.image_tar, args.prefix) if args.image_tar else audit_context(args.root)
    )
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "files"}))
