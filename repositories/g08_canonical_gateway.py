"""Canonical PostgreSQL owner-gateway persistence callbacks.

The adapter assumes its caller has already verified signed application, operator,
D10, D08, and fencing evidence. Database routines repeat current-state, transaction,
scope, and history checks. The gateway executor role is private to the server.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from services.g08_owner_authorization import (
    Authorization,
    ExecutionEvidence,
    ExecutionRequest,
    OperatorAssertion,
    OwnerDenied,
    OwnerReceipt,
    OwnerSnapshot,
    StatusEntry,
)
from services.g08_trust_contract import canonical_claims


class PostgresCanonicalOwnerPersistence:
    """Calls only the additive, least-privilege G08 gateway routines."""

    def acquire_global_lock(self, cursor: Any) -> None:
        cursor.execute("SELECT public.g08_gateway_lock_owner_history()")

    def decision_time(self, cursor: Any) -> datetime:
        cursor.execute("SELECT clock_timestamp()")
        row = cursor.fetchone()
        if row is None or not isinstance(row[0], datetime):
            raise OwnerDenied("PostgreSQL decision time is unavailable")
        return row[0]

    def load(self, cursor: Any, operation_id: str) -> OwnerSnapshot | None:
        cursor.execute(
            "SELECT public.g08_gateway_load_owner_operation(%s)",
            (str(UUID(operation_id)),),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return None
        data = _object(row[0])
        a = _object(data.get("authorization"))
        policy = _object(data.get("policy"))
        authorization = Authorization(
            authorization_id=str(a["authorization_id"]),
            operation_id=str(a["owner_operation_id"]),
            operator_person_ref=str(a["operator_person_ref"]),
            authentication_evidence_ref=str(a["operator_authentication_evidence_ref"]),
            authentication_evidence_sha256=str(a["operator_authentication_evidence_sha256"]),
            valid_from=_datetime(a["valid_from"]),
            valid_to=_datetime(a["valid_to"]),
            tenant_id=_optional_text(policy.get("tenant_id")),
            organization_id=_optional_text(policy.get("organization_id")),
            action=str(a["operation"]),
            target_resource=_optional_text(policy.get("target_resource")),
            policy_version=str(policy.get("version", a["policy_version"])),
            requester_auth_uid=_optional_text(policy.get("requester_uid")),
            requester_person_ref=_optional_text(a.get("requester_person_ref")),
            administrator_id=str(a["administrator_id"]),
            expected_revision=a.get("expected_revision"),
            mutation=_object(a["mutation"]),
            scope_key=str(a["scope_key"]),
            authorization_sha256=str(a["authorization_sha256"]),
            approval_manifest_sha256=str(a["approval_manifest_sha256"]),
            intent_sha256=str(a["intent_sha256"]),
            evidence_ref=str(a["evidence_ref"]),
        )
        history = tuple(
            StatusEntry(
                status_id=str(item["status_id"]),
                revision=int(item["revision"]),
                predecessor_status_id=_optional_text(item.get("predecessor_status_id")),
                predecessor_revision=item.get("predecessor_revision"),
                status=str(item["status"]),
                occurred_at=_datetime(item["occurred_at"]),
            )
            for item in data.get("history", [])
        )
        return OwnerSnapshot(
            authorization,
            history,
            None,
            bool(data.get("consumed", data.get("receipt") is not None)),
        )

    def stage_authorization(
        self, cursor: Any, authorization: Authorization
    ) -> str:
        package = _authorization_row(authorization)
        cursor.execute(
            "SELECT public.g08_gateway_stage_owner_authorization(%s::jsonb)",
            (_json(package),),
        )
        row = cursor.fetchone()
        if row is None or str(row[0]) != authorization.authorization_id:
            raise OwnerDenied("canonical G08 authorization bootstrap did not stage")
        return str(row[0])

    def stage_admission(
        self,
        cursor: Any,
        authorization: Authorization,
        entry: StatusEntry,
        operator: OperatorAssertion,
    ) -> str:
        package = _authorization_row(authorization)
        approvals = self._approval_links(authorization, operator)
        package_json = {
            "authorization": package,
            "assertion": _assertion_row(operator),
            "approvals": approvals,
            "status_id": entry.status_id,
            "evidence_ref": authorization.evidence_ref,
            "rationale": _rationale(authorization),
        }
        cursor.execute(
            "SELECT public.g08_gateway_stage_admission(%s::jsonb)",
            (_json(package_json),),
        )
        result = cursor.fetchone()
        if result is None or str(result[0]) != entry.status_id:
            raise OwnerDenied("canonical G08 admission did not stage")
        return str(result[0])

    def stage_status(
        self,
        cursor: Any,
        authorization: Authorization,
        entry: StatusEntry,
        operator: OperatorAssertion,
    ) -> str:
        package = {
            "assertion": _assertion_row(operator),
            "authorization_id": authorization.authorization_id,
            "status_id": entry.status_id,
            "status": entry.status,
            "expected_predecessor": entry.predecessor_status_id,
            "evidence_ref": authorization.evidence_ref,
            "rationale": _rationale(authorization),
        }
        cursor.execute(
            "SELECT public.g08_gateway_stage_owner_status(%s::jsonb)",
            (_json(package),),
        )
        row = cursor.fetchone()
        if row is None or str(row[0]) != entry.status_id:
            raise OwnerDenied("canonical G08 status transition did not stage")
        return str(row[0])

    def stage_execution(
        self,
        cursor: Any,
        authorization: Authorization,
        request: ExecutionRequest,
        operator: OperatorAssertion,
        evidence: ExecutionEvidence,
    ) -> OwnerReceipt:
        event_id = str(UUID(evidence.event_id))
        evidence_id = str(UUID(evidence.evidence_id))
        assertion_id = str(UUID(operator.assertion_id))
        mutation = _object(authorization.mutation)
        valid_from = mutation.get("valid_from")
        valid_to = mutation.get("valid_to")
        event_time = evidence.decision_time.isoformat()
        canonical_request = {
            "version": "nxr-g08-owner-administration-v1",
            "owner_operation_id": authorization.operation_id,
            "operation": authorization.action,
            "scope_key": authorization.scope_key or "global",
            "authorization_id": authorization.authorization_id,
            "authorization_sha256": authorization.authorization_sha256,
            "approval_manifest_sha256": authorization.approval_manifest_sha256,
            "policy_version": authorization.policy_version,
            "operator": {
                "person_ref": operator.person_ref,
                "authentication_evidence_sha256": operator.authentication_evidence_sha256,
                "verified_auth_uid": operator.verified_auth_uid,
                "db_session_user": operator.db_session_user,
            },
            "procedure_identity": "nxr_g08_postgres_owner_gateway",
            "procedure_version": "candidate-v1",
            "mutation": mutation,
            "idempotency_key": request.idempotency_key,
        }
        if request.canonical_bytes != canonical_claims(canonical_request):
            raise OwnerDenied("request bytes do not match the canonical G08 owner operation")
        package = {
            "scope": {
                "authorization_id": authorization.authorization_id,
                "operation_id": authorization.operation_id,
                "tenant_id": operator.tenant_id,
                "organization_id": operator.organization_id,
                "action": operator.action,
                "target_resource": operator.target_resource,
                "policy_version": operator.policy_version,
                "requester_uid": operator.requester_auth_uid,
                "operator_uid": operator.verified_auth_uid,
                "operator_jti": operator.evidence_jti,
                "approval_ids": list(operator.approval_ids),
                "fence_jti": _fence_jti(evidence.fencing_evidence_ref),
                "fence_generation": evidence.fence_generation,
                "request_digest": request.request_digest,
            },
            "authorization": authorization.authorization_id,
            "idempotency_key": request.idempotency_key,
            "assertion": _assertion_row(operator),
            "administrator": {
                "administrator_id": authorization.administrator_id,
                "subject_auth_uid": mutation.get("subject_auth_uid"),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "revision": 1,
                "revoked_at": None,
                "bootstrap_evidence_ref": authorization.evidence_ref,
                "origin_event_id": event_id,
                "current_event_id": event_id,
            },
            "version": {
                "administrator_id": authorization.administrator_id,
                "subject_auth_uid": mutation.get("subject_auth_uid"),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "revision": 1,
                "revoked_at": None,
                "bootstrap_evidence_ref": authorization.evidence_ref,
                "origin_event_id": event_id,
                "current_event_id": event_id,
                "event_id": event_id,
            },
            "event": {
                "event_id": event_id,
                "administrator_id": authorization.administrator_id,
                "action": authorization.action,
                "before_revision": authorization.expected_revision,
                "after_revision": 1 if authorization.expected_revision is None
                else authorization.expected_revision + 1,
                "request_id": None,
                "requester_auth_uid": None,
                "executor_auth_uid": None,
                "executor_db_role": "private-gateway",
                "execution_mode": "owner_controlled",
                "authorizing_administrator_id": None,
                "authorizing_revision": None,
                "owner_operation_id": authorization.operation_id,
                "intent_sha256": authorization.intent_sha256,
                "request_digest": request.request_digest,
                "fingerprint_version": "nxr-g08-owner-administration-v1",
                "rationale": _rationale(authorization),
                "evidence_ref": authorization.evidence_ref,
                "occurred_at": event_time,
                "correlation_id": event_id,
            },
            "proof": {
                "evidence_id": evidence_id,
                "authorization_id": authorization.authorization_id,
                "owner_operation_id": authorization.operation_id,
                "event_id": event_id,
                "admitted_revision": 1,
                "admitted_status_id": evidence.admitted_status_id,
                "assertion_id": assertion_id,
                "decision_time": event_time,
                "request_digest": request.request_digest,
                "result": evidence.result,
                "technical_evidence_ref": evidence.technical_evidence_ref,
                "technical_evidence_sha256": evidence.technical_evidence_sha256,
                "technical_verifier_ref": evidence.technical_verifier_ref,
                "authority_evidence_ref": evidence.authority_evidence_ref,
                "fencing_evidence_ref": evidence.fencing_evidence_ref,
            },
            "receipt": {
                "event_id": event_id,
                "owner_operation_id": authorization.operation_id,
                "authorization_id": authorization.authorization_id,
                "operation": authorization.action,
                "scope_key": "global",
                "idempotency_key": request.idempotency_key,
                "operator_person_ref": operator.person_ref,
                "operator_authentication_evidence_ref": operator.authentication_evidence_ref,
                "operator_authentication_evidence_sha256": operator.authentication_evidence_sha256,
                "verified_operator_auth_uid": operator.verified_auth_uid,
                "db_session_user": operator.db_session_user,
                "db_effective_role": "private-gateway",
                "procedure_identity": "nxr_g08_postgres_owner_gateway",
                "procedure_version": "candidate-v1",
                "authorization_sha256": authorization.authorization_sha256,
                "approval_manifest_sha256": authorization.approval_manifest_sha256,
                "policy_version": authorization.policy_version,
                "evidence_ref": authorization.evidence_ref,
                "approval_refs": [],
                "fingerprint_version": "nxr-g08-owner-administration-v1",
                "intent_sha256": authorization.intent_sha256,
                "request_digest": request.request_digest,
                "canonical_request": canonical_request,
                "result": evidence.result,
                "occurred_at": event_time,
            },
            "receipt_binding": {
                "event_id": event_id,
                "authorization_id": authorization.authorization_id,
                "owner_operation_id": authorization.operation_id,
                "tenant_id": operator.tenant_id,
                "organization_id": operator.organization_id,
                "policy_version": operator.policy_version,
                "binding_jti": str(uuid4()),
            },
        }
        cursor.execute(
            "SELECT public.g08_gateway_execute_owner_operation(%s::jsonb)",
            (_json(package),),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            raise OwnerDenied("canonical G08 execution gateway returned no receipt")
        outcome = _object(row[0])
        if (
            outcome.get("authorization_id") != authorization.authorization_id
            or outcome.get("operation_id") != authorization.operation_id
            or outcome.get("event_id") != event_id
            or _object(outcome.get("result")) != evidence.result
        ):
            raise OwnerDenied("canonical G08 execution result does not match verified evidence")
        return OwnerReceipt(
            authorization_id=authorization.authorization_id,
            operation_id=authorization.operation_id,
            event_id=event_id,
            evidence_id=evidence_id,
            assertion_id=assertion_id,
            person_ref=operator.person_ref,
            db_session_user=operator.db_session_user,
            idempotency_key=request.idempotency_key,
            canonical_bytes=request.canonical_bytes,
            request_digest=request.request_digest,
            decision_time=evidence.decision_time,
            result=evidence.result,
            tenant_id=operator.tenant_id,
            organization_id=operator.organization_id,
        )

    def read_receipt(
        self,
        cursor: Any,
        authorization_id: str,
        operation_id: str,
        operator: OperatorAssertion,
    ) -> OwnerReceipt | None:
        scope = (
            operator.tenant_id,
            operator.organization_id,
            operator.policy_version,
            operator.verified_auth_uid,
        )
        if any(not isinstance(value, str) or not value.strip() for value in scope):
            raise OwnerDenied("verified tenant-scoped receipt reader identity is required")
        cursor.execute(
            """
            SELECT public.g08_gateway_read_owner_receipt(
                %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid
            )
            """,
            (
                str(UUID(authorization_id)),
                str(UUID(operation_id)),
                str(UUID(operator.tenant_id)),
                str(UUID(operator.organization_id)),
                operator.policy_version,
                str(UUID(operator.verified_auth_uid)),
            ),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return None
        return _receipt(row[0])

    @staticmethod
    def _approval_links(
        authorization: Authorization, operator: OperatorAssertion
    ) -> list[dict[str, Any]]:
        manifest = list(operator.approval_manifest)
        if (
            not manifest
            or tuple(sorted(item.get("approval_ref", "") for item in manifest))
            != operator.approval_ids
            or any(
                item.get("authorization_id") != authorization.authorization_id
                for item in manifest
            )
        ):
            raise OwnerDenied("verified D10 approval manifest is required for G08 admission")
        return manifest


def _authorization_row(authorization: Authorization) -> dict[str, Any]:
    required = (
        authorization.administrator_id,
        authorization.action,
        authorization.mutation,
        authorization.policy_version,
        authorization.requester_auth_uid,
        authorization.authorization_sha256,
        authorization.approval_manifest_sha256,
        authorization.intent_sha256,
        authorization.evidence_ref,
        authorization.requester_person_ref,
    )
    if any(value is None for value in required):
        raise OwnerDenied("complete canonical owner authorization is required")
    return {
        "authorization_id": authorization.authorization_id,
        "owner_operation_id": authorization.operation_id,
        "operation": authorization.action,
        "scope_key": authorization.scope_key or "global",
        "administrator_id": authorization.administrator_id,
        "expected_revision": authorization.expected_revision,
        "mutation": authorization.mutation,
        "parent_operation_id": None,
        "policy_version": authorization.policy_version,
        "requester_person_ref": authorization.requester_person_ref,
        "operator_person_ref": authorization.operator_person_ref,
        "operator_authentication_evidence_ref": authorization.authentication_evidence_ref,
        "operator_authentication_evidence_sha256": authorization.authentication_evidence_sha256,
        "authorization_sha256": authorization.authorization_sha256,
        "approval_manifest_sha256": authorization.approval_manifest_sha256,
        "intent_sha256": authorization.intent_sha256,
        "evidence_ref": authorization.evidence_ref,
        "valid_from": authorization.valid_from,
        "valid_to": authorization.valid_to,
    }


def _assertion_row(assertion: OperatorAssertion) -> dict[str, Any]:
    return {
        "assertion_id": assertion.assertion_id,
        "authorization_id": assertion.authorization_id,
        "owner_operation_id": assertion.operation_id,
        "purpose": assertion.purpose,
        "person_ref": assertion.person_ref,
        "authentication_evidence_ref": assertion.authentication_evidence_ref,
        "authentication_evidence_sha256": assertion.authentication_evidence_sha256,
        "session_binding_ref": assertion.session_binding_ref,
        "db_session_user": assertion.db_session_user,
        "verified_auth_uid": assertion.verified_auth_uid,
        "verifier_ref": assertion.verifier_ref,
        "verified_at": assertion.verified_at,
        "valid_until": assertion.valid_until,
    }


def _receipt(data: Any) -> OwnerReceipt:
    row = _object(data)
    canonical = _object(row["canonical_request"])
    return OwnerReceipt(
        authorization_id=str(row["authorization_id"]),
        operation_id=str(row["owner_operation_id"]),
        event_id=str(row["event_id"]),
        evidence_id=str(row["evidence_id"]),
        assertion_id=str(row["assertion_id"]),
        person_ref=str(row["operator_person_ref"]),
        db_session_user=str(row["db_session_user"]),
        idempotency_key=str(row["idempotency_key"]),
        canonical_bytes=canonical_claims(canonical),
        request_digest=str(row["request_digest"]),
        decision_time=_datetime(row["occurred_at"]),
        result=_object(row["result"]),
        tenant_id=_optional_text(row.get("tenant_id")),
        organization_id=_optional_text(row.get("organization_id")),
    )


def _rationale(authorization: Authorization) -> str:
    mutation = authorization.mutation or {}
    value = mutation.get("rationale")
    if not isinstance(value, str) or not value.strip():
        raise OwnerDenied("signed owner operation rationale is required")
    return value


def _fence_jti(value: str) -> str:
    if not value.startswith("fence:"):
        raise OwnerDenied("verified fencing token identifier is missing")
    return value.removeprefix("fence:")


def _json(value: Any) -> str:
    return json.dumps(
        value,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, UUID)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    raise TypeError(f"unsupported PostgreSQL gateway value: {type(value).__name__}")


def _object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise OwnerDenied("G08 PostgreSQL gateway returned an invalid object")
    return value


def _datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise OwnerDenied("G08 PostgreSQL gateway returned an invalid timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)
