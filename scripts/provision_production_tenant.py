"""Operator-only production tenant provisioning; dry-run is the default."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from services.production_tenant_provisioning_service import (
    ProductionTenantProvisioningService,
    ProvisioningInputError,
    ProvisioningRequest,
    ProvisioningResult,
    validate_request,
)


class _SupabaseOrganizations:
    def __init__(self, client):
        self.client = client

    def get_by_id(self, organization_id):
        rows = (
            self.client.table("organizations")
            .select("id,name,status")
            .eq("id", organization_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def create(self, payload):
        self.client.table("organizations").insert(payload).execute()


class _SupabaseProfiles:
    def __init__(self, client):
        self.client = client

    def get_by_email(self, email):
        rows = (
            self.client.table("users")
            .select("id,email,org_id,role")
            .eq("email", email)
            .limit(1)
            .execute()
            .data
            or []
        )
        return rows[0] if rows else None

    def create(self, payload):
        self.client.table("users").insert(payload).execute()


def _build_live_service():
    from data.supabase_client import supabase_admin

    return ProductionTenantProvisioningService(
        organizations=_SupabaseOrganizations(supabase_admin),
        profiles=_SupabaseProfiles(supabase_admin),
        auth_admin=supabase_admin.auth.admin,
    )


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--organization-name", required=True)
    parser.add_argument("--admin-email", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="validate and summarize locally")
    mode.add_argument("--execute", action="store_true", help="perform approved backend provisioning")
    parser.add_argument(
        "--approved-request",
        action="store_true",
        help="operator assertion that the external request is approved; required with --execute",
    )
    parser.add_argument("--evidence-file", help="optional local operator execution evidence JSON")
    return parser


def _make_result(request: ProvisioningRequest, classification: str, steps: dict[str, str], reason=None):
    return ProvisioningResult(
        request_id=request.request_id,
        organization_id=request.organization_id,
        organization_name=request.organization_name,
        admin_email=request.admin_email,
        role=request.role,
        classification=classification,
        steps=steps,
        reason_code=reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _write_operator_evidence(path: str, evidence: dict) -> bool:
    try:
        with Path(path).open("x", encoding="utf-8") as output:
            output.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    except OSError:
        return False
    return True


def _exit_code(classification: str) -> int:
    return {
        "DRY_RUN": 0,
        "COMPLETE": 0,
        "ALREADY_COMPLETE": 0,
        "INVALID_CONFIGURATION": 2,
        "HARD_CONFLICT": 4,
        "PARTIAL_RECONCILIATION_REQUIRED": 5,
        "REMOTE_OPERATION_FAILED": 6,
    }.get(classification, 6)


def main(argv=None, *, service_factory=None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = validate_request(
            args.request_id,
            args.organization_id,
            args.organization_name,
            args.admin_email,
        )
    except ProvisioningInputError:
        print(json.dumps({"final_classification": "INVALID_ARGUMENTS"}, sort_keys=True))
        return 2

    execute = bool(args.execute)
    if execute and not args.approved_request:
        result = _make_result(
            request,
            "EXECUTION_ACKNOWLEDGEMENT_REQUIRED",
            {"validation": "COMPLETE", "remote_operations": "NOT_RUN"},
            "APPROVED_REQUEST_REQUIRED",
        )
        print(json.dumps(result.operator_evidence() | {"reason_code": result.reason_code}, sort_keys=True))
        return 3

    if not execute:
        has_url = bool(os.getenv("SUPABASE_URL", "").strip())
        has_service_key = bool(
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
        )
        result = _make_result(
            request,
            "DRY_RUN",
            {
                "validation": "COMPLETE",
                "supabase_url_configured": "YES" if has_url else "NO",
                "backend_credential_configured": "YES" if has_service_key else "NO",
                "remote_reads": "NOT_RUN",
                "remote_writes": "NOT_RUN",
            },
        )
        evidence = result.operator_evidence()
        print(json.dumps(evidence, sort_keys=True))
        if args.evidence_file and not _write_operator_evidence(args.evidence_file, evidence):
            print(json.dumps({"evidence_file_status": "WRITE_FAILED"}, sort_keys=True), file=sys.stderr)
            return 6
        return 0

    if not os.getenv("SUPABASE_URL", "").strip() or not (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    ):
        result = _make_result(
            request,
            "INVALID_CONFIGURATION",
            {"validation": "COMPLETE", "remote_operations": "NOT_RUN"},
            "BACKEND_SUPABASE_CONFIGURATION_MISSING",
        )
        print(json.dumps(result.operator_evidence() | {"reason_code": result.reason_code}, sort_keys=True))
        return 2

    try:
        service = (service_factory or _build_live_service)()
        result = service.provision(request)
    except Exception:
        result = _make_result(
            request,
            "REMOTE_OPERATION_FAILED",
            {"execution": "FAILED"},
            "PROVISIONING_EXECUTION_FAILED",
        )

    evidence = result.operator_evidence()
    if result.reason_code:
        evidence["reason_code"] = result.reason_code
    print(json.dumps(evidence, sort_keys=True))
    if args.evidence_file and not _write_operator_evidence(args.evidence_file, result.operator_evidence()):
        print(json.dumps({"evidence_file_status": "WRITE_FAILED"}, sort_keys=True), file=sys.stderr)
        return 6
    return _exit_code(result.classification)


if __name__ == "__main__":
    raise SystemExit(main())