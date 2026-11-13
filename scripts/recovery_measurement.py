"""Record UTC recovery milestones and calculate RPO/RTO from observed events."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EVENTS = (
    "backup_started",
    "backup_completed",
    "last_committed_transaction",
    "simulated_failure",
    "recovery_initiated",
    "database_restore_completed",
    "application_available",
    "customer_validation_completed",
)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("measurement timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def record_event(
    evidence_file: Path, event: str, *, occurred_at: str | None = None
) -> dict[str, str]:
    if event not in EVENTS:
        raise ValueError(f"unknown recovery event: {event}")
    timestamp = _parse_utc(occurred_at) if occurred_at else datetime.now(timezone.utc)
    record = {"event": event, "occurred_at": timestamp.isoformat()}
    evidence_file = Path(evidence_file)
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor = evidence_file.open("a", encoding="utf-8")
    try:
        descriptor.write(json.dumps(record, sort_keys=True) + "\n")
        descriptor.flush()
    finally:
        descriptor.close()
    return record


def summarize(evidence_file: Path) -> dict[str, object]:
    records = [
        json.loads(line)
        for line in Path(evidence_file).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    events: dict[str, datetime] = {}
    for record in records:
        event = record.get("event")
        if event not in EVENTS or event in events:
            raise ValueError("recovery evidence contains unknown or duplicate events")
        events[event] = _parse_utc(record["occurred_at"])
    missing = [event for event in EVENTS if event not in events]
    if missing:
        raise ValueError(f"recovery evidence is missing events: {', '.join(missing)}")
    ordered_pairs = (
        ("backup_started", "backup_completed"),
        ("backup_completed", "simulated_failure"),
        ("last_committed_transaction", "simulated_failure"),
        ("simulated_failure", "recovery_initiated"),
        ("recovery_initiated", "database_restore_completed"),
        ("database_restore_completed", "application_available"),
        ("application_available", "customer_validation_completed"),
    )
    if any(events[start] > events[end] for start, end in ordered_pairs):
        raise ValueError("recovery event timestamps are not in a valid order")
    def seconds(start: str, end: str) -> float:
        return (events[end] - events[start]).total_seconds()

    return {
        "rpo_seconds": seconds("last_committed_transaction", "simulated_failure"),
        "rto_seconds": seconds("simulated_failure", "application_available"),
        "database_restore_seconds": seconds(
            "recovery_initiated", "database_restore_completed"
        ),
        "customer_validation_seconds": seconds(
            "simulated_failure", "customer_validation_completed"
        ),
        "backup_seconds": seconds("backup_started", "backup_completed"),
        "events": {
            event: events[event].isoformat().replace("+00:00", "Z")
            for event in EVENTS
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record")
    record.add_argument("--evidence-file", type=Path, required=True)
    record.add_argument("--event", choices=EVENTS, required=True)
    record.add_argument("--at")
    report = commands.add_parser("summarize")
    report.add_argument("--evidence-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = (
            record_event(args.evidence_file, args.event, occurred_at=args.at)
            if args.command == "record"
            else summarize(args.evidence_file)
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Recovery measurement failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
