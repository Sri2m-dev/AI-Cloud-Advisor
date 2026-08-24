"""Check the public Data Fabric contract surface against a golden baseline."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import types
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

contracts = importlib.import_module("data_fabric.contracts")

BASELINE_TAG = "v1.2.0-data-fabric"
BASELINE_COMMIT = "0a4ab32f4ad431a22ec3ae11cc962cc54c5b15e2"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "data_fabric" / "v1.2.0-contracts.json"


def _type_name(value: Any) -> str:
    """Return a deterministic, implementation-neutral type label."""
    origin = get_origin(value)
    if origin in (Union, types.UnionType):
        return " | ".join(_type_name(item) for item in get_args(value))
    if origin is not None:
        arguments = ", ".join(_type_name(item) for item in get_args(value))
        return f"{_type_name(origin)}[{arguments}]"
    if value is Any:
        return "Any"
    return getattr(value, "__name__", str(value).replace("typing.", ""))


def _field_default(field: Any) -> dict[str, Any]:
    if field.default is not MISSING:
        value = field.default
        if isinstance(value, Enum):
            value = value.value
        return {"kind": "value", "value": value}
    if field.default_factory is not MISSING:
        return {"kind": "factory"}
    return {"kind": "required"}


def build_snapshot() -> dict[str, Any]:
    """Build the deterministic public-contract snapshot."""
    snapshot: dict[str, Any] = {
        "format_version": 1,
        "baseline_tag": BASELINE_TAG,
        "baseline_commit": BASELINE_COMMIT,
        "exports": list(contracts.__all__),
        "contracts": {},
    }
    for name in contracts.__all__:
        contract = getattr(contracts, name)
        if isinstance(contract, type) and issubclass(contract, Enum):
            snapshot["contracts"][name] = {
                "kind": "enum",
                "module": contract.__module__,
                "values": [item.value for item in contract],
            }
            continue
        if not is_dataclass(contract):
            raise TypeError(f"Unsupported public contract: {name}")
        hints = get_type_hints(contract)
        snapshot["contracts"][name] = {
            "kind": "dataclass",
            "module": contract.__module__,
            "frozen": contract.__dataclass_params__.frozen,
            "slots": hasattr(contract, "__slots__"),
            "fields": [
                {
                    "name": field.name,
                    "type": _type_name(hints[field.name]),
                    "default": _field_default(field),
                }
                for field in fields(contract)
            ],
        }
    return snapshot


def compare_snapshots(expected: Any, actual: Any, path: str = "$") -> list[str]:
    """Return deterministic, human-readable differences."""
    if type(expected) is not type(actual):
        return [f"{path}: expected {type(expected).__name__}, got {type(actual).__name__}"]
    if isinstance(expected, dict):
        differences: list[str] = []
        for key in sorted(expected.keys() - actual.keys()):
            differences.append(f"{path}.{key}: missing")
        for key in sorted(actual.keys() - expected.keys()):
            differences.append(f"{path}.{key}: unexpected")
        for key in sorted(expected.keys() & actual.keys()):
            differences.extend(compare_snapshots(expected[key], actual[key], f"{path}.{key}"))
        return differences
    if isinstance(expected, list):
        append_only_contract_path = path.endswith(".fields") or path.endswith(".values")
        if append_only_contract_path and len(actual) >= len(expected):
            actual = actual[: len(expected)]
        if len(expected) != len(actual):
            return [f"{path}: expected {len(expected)} items, got {len(actual)}"]
        differences = []
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            differences.extend(compare_snapshots(expected_item, actual_item, f"{path}[{index}]"))
        return differences
    if expected != actual:
        return [f"{path}: expected {expected!r}, got {actual!r}"]
    return []


def _load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the current snapshot after an approved compatibility-baseline change.",
    )
    arguments = parser.parse_args(argv)
    current = build_snapshot()
    if arguments.write:
        arguments.fixture.parent.mkdir(parents=True, exist_ok=True)
        arguments.fixture.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote compatibility fixture: {arguments.fixture}")
        return 0
    if not arguments.fixture.is_file():
        print(f"Compatibility fixture not found: {arguments.fixture}", file=sys.stderr)
        return 2
    differences = compare_snapshots(_load_fixture(arguments.fixture), current)
    if differences:
        print("Data Fabric compatibility check failed:", file=sys.stderr)
        for difference in differences:
            print(f"- {difference}", file=sys.stderr)
        return 1
    print(
        f"Data Fabric compatibility check passed: {len(current['contracts'])} contracts "
        f"match {current['baseline_tag']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
