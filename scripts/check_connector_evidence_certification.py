"""Run the deterministic WP-004 connector evidence certification gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth.tenant_authorization import TenantAuthorizationContext  # noqa: E402
from connector_certification import (  # noqa: E402
    CertificationCheckpoint,
    ConnectorEvidenceCertifier,
)
from connector_certification.fixtures import aws_pages, microsoft365_pages  # noqa: E402

PROFILES = {
    "aws": ("aws.reference", "AWS", "inventory", aws_pages),
    "microsoft365": (
        "microsoft365.certification",
        "Microsoft 365",
        "directory",
        microsoft365_pages,
    ),
}


def run_gate() -> dict[str, object]:
    context = TenantAuthorizationContext(
        organization_id="wp004-certification-org",
        tenant_id="wp004-certification-tenant",
        subject_id="wp004-certification-runner",
        subject_type="service",
        permissions=frozenset({"connector:run"}),
        source_boundary="connector",
    )
    certifier = ConnectorEvidenceCertifier(
        secret_sentinels=("wp004-synthetic-secret", "wp004-synthetic-token")
    )
    profile_results = []
    for profile, (connector_id, source_system, stream_id, fixture_factory) in PROFILES.items():
        pages = fixture_factory()
        checkpoint = CertificationCheckpoint(
            context.organization_id,
            context.tenant_id,
            connector_id,
            stream_id,
            pages[0].cursor,
        )
        seen = frozenset()
        extracted = accepted = duplicates = 0
        checkpoints = []
        for page in pages:
            result = certifier.certify_page(
                connector_id=connector_id,
                source_system=source_system,
                stream_id=stream_id,
                context=context,
                checkpoint=checkpoint,
                page=page,
                seen_identities=seen,
            )
            extracted += result.extracted
            accepted += result.accepted
            duplicates += result.duplicates
            checkpoints.append(
                {
                    "previous": result.previous_checkpoint.cursor,
                    "resulting": result.resulting_checkpoint.cursor,
                }
            )
            checkpoint = result.resulting_checkpoint
            seen = result.seen_identities
        profile_results.append(
            {
                "profile": profile,
                "connector_id": connector_id,
                "pages": len(pages),
                "extracted": extracted,
                "accepted": accepted,
                "duplicates": duplicates,
                "checkpoints": checkpoints,
                "status": "passed",
            }
        )
    return {
        "gate": "WP-004 Connector Evidence Certification",
        "profile_version": certifier.profile_version,
        "status": "passed",
        "profiles": profile_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable evidence")
    args = parser.parse_args(argv)
    report = run_gate()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        profiles = report["profiles"]
        print(
            "WP-004 connector evidence certification passed: "
            f"{len(profiles)} profiles, "
            f"{sum(item['pages'] for item in profiles)} pages, "
            f"{sum(item['accepted'] for item in profiles)} observations"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
