"""Verify a recovered synthetic V1 workspace through the PostgreSQL app role."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.customer_workflow_service import (
    CustomerWorkflowError,
    CustomerWorkflowService,
)
from services.postgres_customer_workflow_repository import (
    PostgresCustomerWorkflowRepository,
)


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _context(prefix: str, *, jwt_secret: str, issuer: str) -> AuthenticatedTenantContext:
    user_id = os.environ[f"NEXORA_RECOVERY_{prefix}_USER_ID"]
    organization_id = os.environ[f"NEXORA_RECOVERY_{prefix}_ORG_ID"]
    email = os.environ[f"NEXORA_RECOVERY_{prefix}_EMAIL"]
    header = _b64url(b'{"alg":"HS256","typ":"JWT"}')
    claims = _b64url(
        json.dumps(
            {
                "aud": "authenticated",
                "exp": int(time.time()) + 300,
                "iss": issuer,
                "role": "authenticated",
                "sub": user_id,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(
        jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    return AuthenticatedTenantContext(
        organization_id=organization_id,
        organization_name="Synthetic recovery customer",
        user_id=user_id,
        user_email=email,
        role="client_admin",
        authorization_claims=frozenset(),
        tenant_id=organization_id,
        auth_access_token=f"{header}.{claims}.{_b64url(signature)}",
    )


def verify_recovered_workflow(workspace_id: str, evidence_event_id: str) -> dict[str, object]:
    jwt_secret = os.environ["NEXORA_CUSTOMER_WORKFLOW_JWT_SECRET"]
    issuer = os.environ["NEXORA_CUSTOMER_WORKFLOW_JWT_ISSUER"]
    repository = PostgresCustomerWorkflowRepository(
        os.environ["NEXORA_RECOVERY_APP_DSN"],
        key=Path(os.environ["NEXORA_RECOVERY_WORKFLOW_KEY_FILE"]).read_bytes().strip(),
    )
    service = CustomerWorkflowService(
        repository,
        evidence_root=Path(os.environ["NEXORA_RECOVERY_EVIDENCE_ROOT"]),
        evidence_key=Path(os.environ["NEXORA_RECOVERY_EVIDENCE_KEY_FILE"])
        .read_bytes()
        .strip(),
    )
    customer_a = _context("CUSTOMER_A", jwt_secret=jwt_secret, issuer=issuer)
    customer_b = _context("CUSTOMER_B", jwt_secret=jwt_secret, issuer=issuer)

    records = service.resume_workspace(customer_a, workspace_id)
    evidence = next(
        (item for item in records["evidence"] if item["event_id"] == evidence_event_id),
        None,
    )
    if evidence is None:
        raise ValueError("the designated evidence event is absent from the recovered workspace")
    evidence_bytes = service.load_evidence(
        customer_a, workspace_id, evidence_event_id
    )
    if hashlib.sha256(evidence_bytes).hexdigest() != evidence["payload"]["source_sha256"]:
        raise ValueError("recovered evidence plaintext hash does not match its event")
    if not records["asks"] or not records["decisions"] or len(records["approvals"]) < 4:
        raise ValueError("recovered Ask, decision, or multi-stage approval history is incomplete")
    approval_history = [
        item["payload"]["history"]
        for item in records["approvals"]
        if item["event_type"] == "APPROVAL_TRANSITIONED"
    ]
    if {item["actor_role"] for item in approval_history} != {
        "finance",
        "cio",
        "executive",
    }:
        raise ValueError("recovered Finance, CIO, and executive approval history is incomplete")
    if not records["exports"]:
        raise ValueError("evidence-linked export event is missing")
    exported_package = records["exports"][-1]["payload"]["package"]
    if (
        exported_package["evidence"]["record_id"] != evidence_event_id
        or exported_package["approval"]["state"] != "APPROVED"
        or len(exported_package["approval"]["history"]) < 3
    ):
        raise ValueError("recovered evidence-linked export or approval history is invalid")
    try:
        service.resume_workspace(customer_b, workspace_id)
    except PermissionError:
        tenant_isolation = True
    else:
        raise ValueError("Customer B unexpectedly accessed Customer A's workspace")
    return {
        "status": "CUSTOMER_WORKFLOW_RECOVERY_VERIFIED",
        "customer_a_authenticated": True,
        "workspace_recovered": True,
        "evidence_integrity_verified": True,
        "asks_verified": len(records["asks"]),
        "decisions_verified": len(records["decisions"]),
        "approval_events_verified": len(records["approvals"]),
        "exports_verified": len(records["exports"]),
        "tenant_isolation_verified": tenant_isolation,
        "plaintext_or_secret_output": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--evidence-event-id", required=True)
    args = parser.parse_args(argv)
    try:
        print(
            json.dumps(
                verify_recovered_workflow(
                    args.workspace_id, args.evidence_event_id
                ),
                sort_keys=True,
            )
        )
    except (OSError, KeyError, ValueError, PermissionError, CustomerWorkflowError) as error:
        print(f"Recovered customer workflow verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
