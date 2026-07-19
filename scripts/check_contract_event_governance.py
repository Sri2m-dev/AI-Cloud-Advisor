"""Validate the declarative contract and event governance registry."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

toolkit = importlib.import_module("governance.contract_event_governance")
DEFAULT_REGISTRY = ROOT / "governance" / "manifests.json"


def validate_registry(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format_version") != 1:
        raise toolkit.GovernanceValidationError("unsupported registry format_version")
    providers = [toolkit.manifest_from_mapping(item) for item in data.get("providers", ())]
    consumers = [toolkit.consumer_from_mapping(item) for item in data.get("consumers", ())]
    provider_map = {}
    for provider in providers:
        if provider.contract_id in provider_map:
            raise toolkit.GovernanceValidationError(
                f"duplicate provider contract_id: {provider.contract_id}"
            )
        provider_map[provider.contract_id] = provider
    for consumer in consumers:
        provider = provider_map.get(consumer.contract_id)
        if provider is None:
            raise toolkit.GovernanceValidationError(
                f"provider missing for consumer {consumer.consumer}"
            )
        consumer.verify(provider)
    return len(providers), len(consumers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    arguments = parser.parse_args(argv)
    try:
        providers, consumers = validate_registry(arguments.registry)
    except (OSError, json.JSONDecodeError, KeyError, toolkit.GovernanceValidationError) as exc:
        print(f"Contract/event governance check failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Contract/event governance check passed: {providers} providers, " f"{consumers} consumers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
