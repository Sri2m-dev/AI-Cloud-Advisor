"""Prepare/hash the qualification package without importing any database driver."""
import argparse
import hashlib
import json
import re
from pathlib import Path

MIGRATIONS = [
    "database/contracts/g08_m2a/S020_integrity.sql",
    "database/contracts/g08_m2a/A020A_enforcement.sql",
    "database/contracts/g08_m2a/A020A_private_writer.sql",
    "database/contracts/g08_m2b/S021_owner_authorization.sql",
    "database/contracts/g08_m2b/A021_owner_integrity.sql",
    "database/contracts/g08_m2b/A021_owner_interfaces.sql",
    "database/contracts/g08_m2c/A022_result_link_integrity.sql",
]


def prepare(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [Path(p) for p in MIGRATIONS]
    paths += sorted(Path("database/contracts/g08_m2c/qualification").glob("*.sql"))
    paths += [Path("database/contracts/g08_m2c/qualification/unknown_commit_probe.py")]
    paths += [Path("tests/database_integrity/postgres_qualification.sql"),
              Path("tests/owner_authorization/postgres_qualification.sql"),
              Path("tests/owner_authorization/postgres_race_session_a.sql"),
              Path("tests/owner_authorization/postgres_race_session_b.sql")]
    for path in paths:
        for line in path.read_text().splitlines():
            if line.startswith("\\ir ") and not (path.parent / line[4:]).resolve().is_file():
                raise ValueError(f"missing include in {path}")
    result = {"status": "PREPARED_NOT_EXECUTED", "migration_order": MIGRATIONS,
              "sha256": {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              "postgresql_executed": False, "authorized_local_target_identified": False}
    known = {"auth.users"}
    order_issues = []
    for name in MIGRATIONS[:6]:
        source = Path(name).read_text()
        for match in re.finditer(r"(CREATE TABLE|REFERENCES)\s+((?:public|auth)\.\w+)", source):
            if match[1] == "CREATE TABLE":
                if match[2] in known:
                    order_issues.append(f"duplicate table in {name}: {match[2]}")
                known.add(match[2])
            elif match[2] not in known:
                order_issues.append(f"forward or missing FK target in {name}: {match[2]}")
    assessment = {"method": "regex dependency inspection, NOT SQL parsing or execution",
                  "tables_defined": len(known)-1, "order_issues": order_issues,
                  "original_migrations": MIGRATIONS[:6], "additive_correction": MIGRATIONS[6],
                  "qualification_status": "NOT_POSTGRESQL_QUALIFIED"}
    (output_dir / "six-migration-compatibility.json").write_text(json.dumps(assessment,indent=2)+"\n")
    if order_issues:
        raise ValueError("migration dependency inspection failed")
    (output_dir / "qualification-manifest.json").write_text(json.dumps(result, indent=2)+"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.output_dir)
    print(json.dumps({"status": result["status"], "files": len(result["sha256"])}))
