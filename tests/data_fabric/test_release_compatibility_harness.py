from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_data_fabric_compatibility.py"
FIXTURE = ROOT / "tests" / "fixtures" / "data_fabric" / "v1.2.0-contracts.json"


def _load_harness():
    spec = importlib.util.spec_from_file_location("data_fabric_compatibility", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v1_2_0_public_contract_snapshot_is_unchanged() -> None:
    harness = _load_harness()
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert harness.compare_snapshots(expected, harness.build_snapshot()) == []


def test_snapshot_generation_is_deterministic() -> None:
    harness = _load_harness()

    assert harness.build_snapshot() == harness.build_snapshot()


def test_harness_reports_a_precise_contract_drift_path() -> None:
    harness = _load_harness()
    expected = harness.build_snapshot()
    changed = copy.deepcopy(expected)
    changed["contracts"]["EnterpriseEntity"]["fields"][0]["name"] = "renamed_id"

    assert harness.compare_snapshots(expected, changed) == [
        "$.contracts.EnterpriseEntity.fields[0].name: expected 'id', got 'renamed_id'"
    ]


def test_harness_allows_only_append_only_contract_extensions() -> None:
    harness = _load_harness()
    expected = harness.build_snapshot()
    extended = copy.deepcopy(expected)
    extended["contracts"]["EntityType"]["values"].append("future_type")

    assert harness.compare_snapshots(expected, extended) == []

    removed = copy.deepcopy(expected)
    removed["contracts"]["EntityType"]["values"].pop()
    assert harness.compare_snapshots(expected, removed)


def test_command_line_check_passes_against_committed_fixture() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture", str(FIXTURE)],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "10 contracts match v1.2.0-data-fabric" in result.stdout
