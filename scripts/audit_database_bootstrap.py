"""Offline, conservative inventory for CMP-P6-DEF-001; never executes SQL.

This is lexical/AST evidence, not a PostgreSQL parser or a deployment runner.
Unknown dynamic calls and missing definitions are deliberately retained.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREREQUISITES = "supabase/bootstrap/public_prerequisites.sql"
IDENT = r'"?[a-zA-Z_][\w$]*"?'
NAME = rf"{IDENT}(?:\s*\.\s*{IDENT})?"
CREATE = re.compile(
    rf"\bcreate\s+(?:or\s+replace\s+)?(materialized\s+view|table|view|function|sequence|schema|extension)"
    rf"\s+(?:if\s+not\s+exists\s+)?({NAME})",
    re.I,
)
REFERENCE = re.compile(rf"\b(public|data_fabric|auth)\s*\.\s*({IDENT})", re.I)
EXCLUDED_PY = ("archive/", "backup_unused/", "tests/", "scripts/", "mock_data/", "demo_ceo/")


def tracked(suffix: str) -> list[str]:
    return sorted(
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", f"*{suffix}"],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )


def digest(path: str) -> str:
    # Git checkouts may convert LF/CRLF. Hash SQL text with canonical LF so a
    # fresh Linux clone and this Windows checkout certify the same statements.
    return hashlib.sha256((ROOT / path).read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def clean_name(name: str) -> str:
    return re.sub(r"\s+", "", name.replace('"', "")).lower()


def strip_comments(sql: str) -> str:
    # Preserve offsets/line numbers. Quoted literals and dollar bodies remain
    # intact; dollar bodies intentionally expose SQL-language dependencies.
    pattern = r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*[\s\S]*?\*/"
    return re.sub(
        pattern,
        lambda m: re.sub(r"[^\n]", " ", m[0]) if m[0].startswith(("--", "/*")) else m[0],
        sql,
    )


def sql_inventory(paths: list[str]) -> tuple[list[dict], dict[str, list[str]]]:
    records = []
    definitions: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        sql = strip_comments((ROOT / path).read_text(encoding="utf-8-sig"))
        objects = []
        for match in CREATE.finditer(sql):
            kind, name = match.group(1).lower(), clean_name(match.group(2))
            if "." not in name and kind not in ("schema", "extension"):
                name = ("sqlite." if "universal_evidence/" in path else "public.") + name
            objects.append(
                {"kind": kind, "name": name, "line": sql.count("\n", 0, match.start()) + 1}
            )
            definitions[name].append(path)
        for match in re.finditer(
            rf"\balter\s+function\s+({NAME})\s*\([^;]*?\)\s+rename\s+to\s+({IDENT})",
            sql,
            re.I,
        ):
            source = clean_name(match[1])
            target = source.rsplit(".", 1)[0] + "." + clean_name(match[2])
            objects.append(
                {
                    "kind": "renamed_function",
                    "name": target,
                    "renamed_from": source,
                    "line": sql.count("\n", 0, match.start()) + 1,
                }
            )
            definitions[target].append(path)
        references = sorted(set(clean_name(a + "." + b) for a, b in REFERENCE.findall(sql)))
        structural = []
        patterns = {
            "index": rf"\bcreate\s+(?:unique\s+)?index\s+(?:if\s+not\s+exists\s+)?({NAME})",
            "trigger": rf"\bcreate\s+(?:or\s+replace\s+)?trigger\s+({IDENT})",
            "policy": r'\bcreate\s+policy\s+("[^"]+"|\w+)',
            "constraint": rf"\bconstraint\s+({IDENT})",
            "added_column": rf"\badd\s+column\s+(?:if\s+not\s+exists\s+)?({IDENT})",
        }
        for kind, pattern in patterns.items():
            for match in re.finditer(pattern, sql, re.I):
                structural.append(
                    {
                        "kind": kind,
                        "name": clean_name(match[1]),
                        "line": sql.count("\n", 0, match.start()) + 1,
                    }
                )
        # This flag is intentionally conservative: DML inside an RPC counts.
        # It means manual schema-only review is needed, not that RPCs seed data.
        flags = []
        for label, pattern in {
            "contains_dml_review_context": r"\b(insert\s+into|update\s+public\.|copy\s+)",
            "broad_grant_or_policy": r"\bgrant\s+all\b|using\s*\(\s*true\s*\)",
            "literal_uuid_review_required": r"'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}'",
            "explicit_failure_guard": r"raise\s+exception",
        }.items():
            if re.search(pattern, sql, re.I):
                flags.append(label)
        records.append(
            {
                "path": path,
                "sha256": digest(path),
                "objects": objects,
                "structural_objects": structural,
                "qualified_references": references,
                "review_flags": flags,
            }
        )
    return records, dict(sorted(definitions.items()))


def application_inventory(
    paths: list[str], definitions: dict
) -> tuple[list[dict], list[dict], list[dict]]:
    calls, dynamic, constants = [], [], []
    for path in paths:
        if path.startswith(EXCLUDED_PY):
            continue
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                name = clean_name(node.value)
                if "public." + name in definitions:
                    constants.append(
                        {"path": path, "line": node.lineno, "object": "public." + name}
                    )
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("table", "from_", "rpc")
                and node.args
            ):
                continue
            arg = node.args[0]
            record = {"path": path, "line": node.lineno, "operation": node.func.attr}
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                name = arg.value
                # Unqualified API names may have a schema-bound client. Never
                # silently assume those calls necessarily address public.
                candidates = [
                    n for n in definitions if n in (name, "public." + name, "data_fabric." + name)
                ]
                record.update(
                    name=name,
                    definition_candidates=candidates,
                    namespace="requires_client_schema_review",
                )
                calls.append(record)
            else:
                record["expression"] = ast.unparse(arg)
                dynamic.append(record)
    return calls, dynamic, constants


def build_inventory() -> dict:
    records, definitions = sql_inventory(sorted(set(tracked(".sql")) | {PREREQUISITES}))
    calls, dynamic, constants = application_inventory(tracked(".py"), definitions)
    used = {c["object"] for c in constants}
    used.update(n for c in calls for n in c["definition_candidates"])
    dated = [r for r in records if r["path"].startswith("supabase/migrations/")]
    used.update(n for r in dated for n in r["qualified_references"])
    # Recursively retain dependencies of all evidenced object providers.
    while True:
        previous = set(used)
        for record in records:
            if any(o["name"] in used for o in record["objects"]):
                used.update(record["qualified_references"])
        if used == previous:
            break
    for record in records:
        path = record["path"]
        if path == PREREQUISITES:
            classification, reason = (
                "CURRENT_REQUIRED",
                (
                    "Versioned public prerequisites, including canonical v1 approvals; "
                    "ordered-chain contract is checked separately."
                ),
            )
        elif path.startswith(("supabase/migrations/", "migrations/")):
            classification, reason = (
                "CURRENT_REQUIRED",
                "Existing versioned chain; preserve unchanged.",
            )
        elif path.startswith(("archive/", "backup_unused/", "backups/")):
            classification, reason = (
                "UNSAFE_TO_REPLAY",
                "Historical dump; extract reviewed DDL only, never replay.",
            )
        elif path.endswith("tenant_rls_policies.sql"):
            classification, reason = (
                "SUPERSEDED",
                "Fail-closed pointer to dated security reconciliation.",
            )
        elif (
            "literal_uuid_review_required" in record["review_flags"]
            or "broad_grant_or_policy" in record["review_flags"]
        ):
            classification, reason = (
                "UNSAFE_TO_REPLAY",
                "Literal tenant/seed identity or broad authorization; manual extraction required.",
            )
        elif any(o["name"] in used for o in record["objects"]):
            classification, reason = (
                "CURRENT_REQUIRED",
                (
                    "Contains required-object evidence; NOT approval to replay whole "
                    "file or choose among conflicting definitions."
                ),
            )
        else:
            classification, reason = (
                "UNKNOWN",
                (
                    "No sufficient evidence to declare this script optional or "
                    "obsolete; retain for review."
                ),
            )
        record.update(classification=classification, classification_reason=reason)
    available = {"auth.jwt", "auth.uid", "auth.role"}
    edges = []
    for record in dated:
        created = {o["name"] for o in record["objects"]}
        references = set(record["qualified_references"])
        edges.append(
            {
                "migration": record["path"],
                "creates_or_replaces": sorted(created),
                "references": sorted(references),
                "pre_chain_or_unresolved": sorted(references - available - created),
                "providers": {n: definitions.get(n, []) for n in sorted(references)},
            }
        )
        available.update(created)
    return {
        "status": bootstrap_contract()["status"],
        "limitations": [
            (
                "Lexical SQL and Python AST inventory, not PostgreSQL execution or "
                "semantic validation."
            ),
            (
                "Qualified references include function bodies; unqualified SQL and "
                "dynamic SQL require manual review."
            ),
            (
                "Calls and constants are conservative candidates, not proof of "
                "reachability or public client namespace."
            ),
            (
                "Columns inside CREATE TABLE and expression/type dependencies "
                "require source-level review."
            ),
            (
                "CURRENT_REQUIRED means evidence is needed; historical files are "
                "never an execution allowlist."
            ),
        ],
        "sql_files": records,
        "definition_sources": definitions,
        "application_calls": calls,
        "dynamic_calls": dynamic,
        "known_object_string_references": constants,
        "missing_literal_call_definitions": [c for c in calls if not c["definition_candidates"]],
        "dated_dependency_graph": edges,
    }


CONNECTOR_FILES = (
    "migrations/connectors/0001_live_source_control.sql",
    "migrations/connectors/0002_add_m365_provider.sql",
)


def bootstrap_contract():
    """Check current ordered authority definitions; never claim PostgreSQL execution."""
    chains = {
        prefix: sorted(tracked(".sql"))
        for prefix in (
            "supabase/migrations/",
            "migrations/data_fabric/",
            "migrations/connectors/",
        )
    }
    chains = {
        prefix: [p for p in paths if p.startswith(prefix)] for prefix, paths in chains.items()
    }
    paths = [
        PREREQUISITES,
        *chains["supabase/migrations/"],
        *chains["migrations/data_fabric/"],
        *chains["migrations/connectors/"],
    ]
    blockers = []
    if not set(CONNECTOR_FILES) <= set(paths):
        blockers.append("Required WS2/WS3 connector migration is missing")
    for prefix, expected in (("migrations/data_fabric/", 23), ("migrations/connectors/", 2)):
        numbers = [int(Path(p).name[:4]) for p in chains[prefix]]
        if numbers != list(range(1, max(expected, len(numbers)) + 1)):
            blockers.append("Missing or unordered chain: " + prefix)
    if len(chains["supabase/migrations/"]) < 17:
        blockers.append("Required dated v1 migration chain is incomplete")
    missing = [p for p in paths if not (ROOT / p).is_file()]
    blockers.extend("Missing migration: " + p for p in missing)
    available = {"auth.jwt", "auth.uid", "auth.role", "auth.users"}
    records, _ = sql_inventory(
        [p for p in paths if p not in missing and not p.startswith("migrations/connectors/")]
    )
    for record in records:
        created = {item["name"] for item in record["objects"]}
        unresolved = set(record["qualified_references"]) - available - created
        # Schemas themselves are providers, not a missing table/RPC.
        unresolved -= {"auth", "public", "data_fabric"}
        if unresolved:
            blockers.append(record["path"] + ": unresolved " + ", ".join(sorted(unresolved)))
        available.update(created)
    required = {
        "public.nexora_v1_approval_requests",
        "public.nexora_v1_approval_history",
        "public.tenant_cloud_financial_posture_v1",
        "data_fabric.source_facts",
    }
    if required - available:
        blockers.append(
            "Missing current authority definitions: " + ", ".join(sorted(required - available))
        )
    for path in (
        "data_fabric/source_facts/persistence.py",
        "migrations/universal_evidence/0001_create_lifecycle_state.sql",
    ):
        if not (ROOT / path).is_file():
            blockers.append("Missing local persistence initializer: " + path)
    return {
        "status": "BLOCKED" if blockers else "READY_FOR_REPLAY",
        "blockers": blockers,
        "validation": "Static ordered-definition and migration-completeness checks only",
        "postgres_replay": "NOT_EXECUTED",
        "external_prerequisites": [
            "Supabase auth schema/functions and roles",
            "Empty public application schema",
        ],
    }


def build_manifest() -> dict:
    contract = bootstrap_contract()
    return {
        "defect": "V1_1_ACCEPTANCE_C",
        "status": contract["status"],
        "executable": not contract["blockers"],
        "hash_format": (
            "SHA-256 of UTF-8 SQL text with LF newlines; portable across Git " "EOL conversion"
        ),
        "reason": (
            "Current canonical authority chains; legacy inventory is not a " "deployment allowlist."
        ),
        "blockers": contract["blockers"],
        "contract": contract,
        "historical_evidence": "docs/cmp/CMP-P6-RC-001/REPORT.md",
        "steps": [
            {
                "order": 1,
                "name": "public_bootstrap",
                "path": PREREQUISITES,
                "sha256": digest(PREREQUISITES),
                "status": "SCHEMA_ONLY_CURRENT_CHAIN_PREREQUISITES",
            },
            {
                "order": 2,
                "name": "dated_public",
                "files": [
                    {"path": p, "sha256": digest(p)}
                    for p in tracked(".sql")
                    if p.startswith("supabase/migrations/")
                ],
            },
            {
                "order": 3,
                "name": "data_fabric",
                "files": [
                    {"path": p, "sha256": digest(p)}
                    for p in tracked(".sql")
                    if p.startswith("migrations/data_fabric/")
                ],
            },
            {
                "order": 4,
                "name": "universal_evidence_local_lifecycle",
                "engine": "sqlite",
                "files": [
                    {
                        "path": "migrations/universal_evidence/0001_create_lifecycle_state.sql",
                        "sha256": digest(
                            "migrations/universal_evidence/0001_create_lifecycle_state.sql"
                        ),
                    }
                ],
                "initialization": (
                    "Existing app startup initializer / SQLiteLifecycleRepository; "
                    "separate persistent local store, never Supabase SQL."
                ),
            },
            {
                "order": 5,
                "name": "source_fact_local_authority",
                "engine": "sqlite",
                "initializer": "SQLiteSourceFactRepository",
                "path": "data_fabric/source_facts/persistence.py",
                "sha256": digest("data_fabric/source_facts/persistence.py"),
            },
            {
                "order": 6,
                "name": "live_connectors",
                "engine": "sqlite",
                "requires": ["source_fact_local_authority"],
                "files": [
                    {"path": p, "sha256": digest(p)}
                    for p in tracked(".sql")
                    if p.startswith("migrations/connectors/")
                ],
                "initialization": (
                    "LiveSourceRepository; idempotent version-guarded local " "initialization"
                ),
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in [
        ("schema_inventory.json", build_inventory()),
        ("migration_manifest.json", build_manifest()),
    ]:
        (args.output_dir / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(
        "Offline inventory written. Deployment status: "
        + build_manifest()["status"]
        + " (no SQL executed)."
    )


if __name__ == "__main__":
    main()
