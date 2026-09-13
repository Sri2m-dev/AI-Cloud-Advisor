"""Fail-closed coverage for the new v1 application schema contract."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/cmp/CMP-P6-DEF-003/recovery_matrix.json"
CONTRACT = ROOT / "docs/cmp/CMP-P6-SC-001/application_schema_contract.md"


def _contract_objects() -> set[str]:
    text = CONTRACT.read_text(encoding="utf-8")
    return set(re.findall(r"\| `([^`]+)` \| (?:V1_REQUIRED|V1_OPTIONAL|LEGACY_UNREACHABLE) \|", text))


def test_v1_contract_covers_exact_def003_object_set():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    expected = {item["name"] for item in matrix["objects"]}
    assert len(expected) == 34
    assert _contract_objects() == expected
    required_rows = re.findall(r"\| `([^`]+)` \| V1_REQUIRED \|", CONTRACT.read_text(encoding="utf-8"))
    assert len(required_rows) == 8
    assert "approval_audit" not in required_rows


def test_v1_contract_has_no_speculative_e5_authority():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "E5: convenience or speculation; prohibited" in text
    assert "No E5 fields" in text
    assert "Data Fabric remains the canonical" in text
    assert "Existing P1/P2 financial authorities remain canonical" in text


def test_v1_contract_remains_blocked_until_required_contracts_are_proven():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "**Status: BLOCKED_V1_SCHEMA_CONTRACT**" in text
    for name in (
        "application_registry",
        "application_spend_mapping",
        "approval_history",
        "approval_requests",
        "mart_application_spend",
        "mart_enterprise_spend",
        "mart_enterprise_spend_v2",
        "technology_inventory",
    ):
        assert f"`{name}`" in text
    assert "No DDL" in text
