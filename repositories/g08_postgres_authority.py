"""PostgreSQL-backed G08 D10, fencing, UoW, and tenant receipt adapters.

These adapters require the unapplied D10 candidate schema and separately
reviewed database privileges. They are not wired into the live application.
Canonical owner writes remain delegated to an injected persistence gateway;
the currently applied G08 control RPC intentionally fails closed.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Protocol
from uuid import UUID

import psycopg2
from psycopg2.extensions import TRANSACTION_STATUS_INTRANS
from psycopg2.extras import register_uuid

from auth.authenticated_tenant import ProtectedWorkflowUnavailable
from services.g08_owner_authorization import (
    Authorization,
    ExecutionEvidence,
    ExecutionRequest,
    OperatorAssertion,
    OwnerAuthorizationCoordinator,
    OwnerDenied,
    OwnerDependencyUnavailable,
    OwnerReceipt,
    OwnerSnapshot,
    OwnerUnitOfWork,
    StatusEntry,
)
from services.g08_transaction_boundary import DurableReceipt, execute_once
from services.g08_trust_contract import (
    ApplicationSessionVerifier,
    D10PolicyAuthority,
    SignedEnvelope,
    SignedEvidenceVerifier,
)


class PostgresG08PolicyAuthority(D10PolicyAuthority):
    """Reads signed D10 records and serializes authorization updates on its state row.

    The supplied psycopg2 connection must be the same connection/transaction used by
    ``PostgresG08UnitOfWork``. Trusted policy/revocation writers must update the
    corresponding authority-state row before appending changes.
    """

    def __init__(self, connection: Any) -> None:
        if (
            connection is None
            or getattr(connection, "closed", True)
            or not callable(getattr(connection, "cursor", None))
        ):
            raise OwnerDependencyUnavailable("a live PostgreSQL D10 connection is required")
        register_uuid(conn_or_curs=connection)
        self.connection = connection

    def _cursor(self):
        if self.connection.closed:
            raise OwnerDependencyUnavailable("G08 policy database connection is closed")
        try:
            return self.connection.cursor()
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("G08 policy database is unavailable") from error

    def _read_bundle(
        self,
        authorization_id: str,
        operation_id: str | None,
        tenant_id: str | None,
        organization_id: str | None,
    ) -> dict[str, Any]:
        if not all((operation_id, tenant_id, organization_id)):
            raise OwnerDenied("tenant and operation scope are required for D10 reads")
        cursor = self._cursor()
        try:
            cursor.execute(
                """
                SELECT public.g08_d10_gateway_read_bundle(
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid
                )
                """,
                (
                    _uuid(authorization_id),
                    _uuid(operation_id),
                    _uuid(tenant_id),
                    _uuid(organization_id),
                ),
            )
            row = cursor.fetchone()
        except psycopg2.Error as error:
            if error.pgcode == "42501":
                raise OwnerDenied(
                    "D10 authority is missing or outside the requested scope"
                ) from error
            raise OwnerDependencyUnavailable("current D10 policy version is unavailable") from error
        finally:
            cursor.close()
        if row is None or row[0] is None:
            raise OwnerDependencyUnavailable("current D10 authority bundle is unavailable")
        bundle = _json_object(row[0])
        if bundle.get("authority_class") != "SYNTHETIC_QUALIFICATION":
            raise OwnerDenied("D10 authority is not accepted for isolated synthetic qualification")
        if not isinstance(bundle.get("approvals"), list):
            raise OwnerDependencyUnavailable("persisted D10 approval bundle is malformed")
        return bundle

    @staticmethod
    def _bundle_policy(
        bundle: Mapping[str, Any], requested_version: str | None = None
    ) -> SignedEnvelope:
        if (
            requested_version is not None
            and bundle.get("current_policy_version") != requested_version
        ):
            raise OwnerDenied("D10 policy version is stale")
        raw = _json_object(bundle.get("policy"))
        signature = raw.get("signature_hex")
        if not isinstance(signature, str):
            raise OwnerDependencyUnavailable("persisted D10 policy signature is malformed")
        try:
            return SignedEnvelope(
                str(raw["issuer_key_id"]),
                _json_object(raw.get("claims")),
                bytes.fromhex(signature),
            )
        except (KeyError, ValueError) as error:
            raise OwnerDependencyUnavailable(
                "persisted D10 policy envelope is malformed"
            ) from error

    def current_version(
        self,
        authorization_id: str,
        operation_id: str | None = None,
        tenant_id: str | None = None,
        organization_id: str | None = None,
    ) -> str:
        bundle = self._read_bundle(authorization_id, operation_id, tenant_id, organization_id)
        version = bundle.get("current_policy_version")
        if not isinstance(version, str) or not version:
            raise OwnerDependencyUnavailable("current D10 policy version is malformed")
        return version

    def policy(
        self,
        authorization_id: str,
        version: str,
        operation_id: str | None = None,
        tenant_id: str | None = None,
        organization_id: str | None = None,
    ) -> SignedEnvelope:
        bundle = self._read_bundle(authorization_id, operation_id, tenant_id, organization_id)
        return self._bundle_policy(bundle, version)

    def approvals(
        self,
        authorization_id: str,
        version: str,
        operation_id: str | None = None,
        tenant_id: str | None = None,
        organization_id: str | None = None,
    ) -> tuple[SignedEnvelope, ...]:
        bundle = self._read_bundle(authorization_id, operation_id, tenant_id, organization_id)
        self._bundle_policy(bundle, version)
        result = []
        for raw_value in bundle["approvals"]:
            raw = _json_object(raw_value)
            signature = raw.get("signature_hex")
            if not isinstance(signature, str):
                raise OwnerDependencyUnavailable("persisted D10 approval signature is malformed")
            try:
                result.append(
                    SignedEnvelope(
                        str(raw["issuer_key_id"]),
                        _json_object(raw.get("claims")),
                        bytes.fromhex(signature),
                    )
                )
            except (KeyError, ValueError) as error:
                raise OwnerDependencyUnavailable(
                    "persisted D10 approval envelope is malformed"
                ) from error
        return tuple(result)

    def is_approval_revoked(self, approval_id: str, authorization_id: str | None = None) -> bool:
        return self._is_revoked(
            "APPROVAL",
            approval_id,
            authorization_id,
        )

    def is_authorization_revoked(self, authorization_id: str) -> bool:
        return self._is_revoked("AUTHORIZATION", authorization_id, authorization_id)

    def is_evidence_revoked(self, evidence_jti: str, authorization_id: str | None = None) -> bool:
        return self._is_revoked("OPERATOR_EVIDENCE", evidence_jti, authorization_id)

    def is_fencing_token_revoked(
        self, evidence_jti: str, authorization_id: str | None = None
    ) -> bool:
        return self._is_revoked("FENCING_TOKEN", evidence_jti, authorization_id)

    def append_policy(
        self,
        authorization_id: str,
        version: str,
        envelope: SignedEnvelope,
        verifier: SignedEvidenceVerifier,
        decision_time,
    ) -> None:
        """Persist a signed immutable policy and atomically advance its current head."""
        self._require_transaction()
        claims = verifier.verify_subject_bound(envelope, decision_time)
        policy_id = _claim_text(claims, "policy_id")
        operation_id = _claim_text(claims, "operation_id")
        tenant_id = _claim_text(claims, "tenant_id")
        organization_id = _claim_text(claims, "organization_id")
        if (
            _claim_text(claims, "authorization_id") != authorization_id
            or _claim_text(claims, "version") != version
            or _claim_text(claims, "authority_class") != "SYNTHETIC_QUALIFICATION"
        ):
            raise OwnerDenied("signed D10 policy does not match the requested authority scope")
        valid_from = _claim_datetime(claims, "not_before")
        valid_to = _claim_datetime(claims, "expires_at")
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT public.g08_d10_gateway_append_policy(
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s,
                    %s::jsonb, %s, %s, %s
                )
                """,
                (
                    _uuid(authorization_id),
                    _uuid(operation_id),
                    _uuid(tenant_id),
                    _uuid(organization_id),
                    version,
                    policy_id,
                    envelope.key_id,
                    _claim_text(claims, "jti"),
                    json.dumps(claims, sort_keys=True),
                    envelope.signature,
                    valid_from,
                    valid_to,
                )
            )
        except psycopg2.Error as error:
            if error.pgcode in {"42501", "23505"}:
                raise OwnerDenied("synthetic D10 policy persistence was rejected") from error
            raise OwnerDependencyUnavailable("signed D10 policy persistence failed") from error
        finally:
            cursor.close()

    def append_approval(
        self,
        authorization_id: str,
        version: str,
        envelope: SignedEnvelope,
        policy_verifier: SignedEvidenceVerifier,
        approval_verifier: SignedEvidenceVerifier,
        decision_time,
    ) -> None:
        """Persist a signed approval only for the locked current policy version."""
        self._require_transaction()
        cursor = self.connection.cursor()
        try:
            approval = approval_verifier.verify_subject_bound(envelope, decision_time)
            operation_id = _claim_text(approval, "operation_id")
            tenant_id = _claim_text(approval, "tenant_id")
            organization_id = _claim_text(approval, "organization_id")
            policy = policy_verifier.verify_subject_bound(
                self.policy(
                    authorization_id,
                    version,
                    operation_id,
                    tenant_id,
                    organization_id,
                ),
                decision_time,
            )
            fields = (
                "approval_id", "policy_id", "policy_version", "authorization_id",
                "operation_id", "tenant_id", "organization_id", "action",
                "target_resource", "requester_uid", "approver_uid",
            )
            for field in fields:
                _claim_text(approval, field)
            for field in (
                "policy_id", "version", "authorization_id", "operation_id",
                "tenant_id", "organization_id", "action", "target_resource",
                "requester_uid",
            ):
                approval_field = "policy_version" if field == "version" else field
                if approval[approval_field] != policy[field]:
                    raise OwnerDenied("approval is not bound to the exact signed D10 policy scope")
            if approval["approver_uid"] == approval["requester_uid"]:
                raise OwnerDenied("requester and approver must be independent identities")
            cursor.execute(
                """
                SELECT public.g08_d10_gateway_append_approval(
                    %s::uuid, %s::uuid, %s, %s::uuid, %s, %s,
                    %s::jsonb, %s, %s, %s
                )
                """,
                (
                    _uuid(authorization_id),
                    _uuid(operation_id),
                    version,
                    _uuid(approval["approval_id"]),
                    envelope.key_id,
                    _claim_text(approval, "jti"),
                    json.dumps(approval, sort_keys=True),
                    envelope.signature,
                    _claim_datetime(approval, "iat"),
                    _claim_datetime(approval, "exp"),
                ),
            )
        except (OwnerDenied, OwnerDependencyUnavailable):
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("signed D10 approval persistence failed") from error
        finally:
            cursor.close()

    def append_revocation(
        self,
        authorization_id: str,
        envelope: SignedEnvelope,
        verifier: SignedEvidenceVerifier,
        decision_time,
    ) -> None:
        """Persist signed revocation under the same authorization-state row lock as execution."""
        self._require_transaction()
        claims = verifier.verify_subject_bound(envelope, decision_time)
        if _claim_text(claims, "authorization_id") != authorization_id:
            raise OwnerDenied("revocation is bound to another authorization")
        subject_type = _claim_text(claims, "subject_type")
        subject_id = _claim_text(claims, "subject_id")
        revoked_at = _claim_datetime(claims, "revoked_at")
        revocation_id = _uuid(_claim_text(claims, "revocation_id"))
        if subject_type not in {
            "AUTHORIZATION", "APPROVAL", "OPERATOR_EVIDENCE", "FENCING_TOKEN"
        }:
            raise OwnerDenied("unsupported D10 revocation subject")
        if subject_type == "AUTHORIZATION" and subject_id != authorization_id:
            raise OwnerDenied("authorization revocation subject does not match its scope")
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT public.g08_d10_gateway_append_revocation(
                    %s::uuid, %s::uuid, %s, %s, %s, %s,
                    %s::jsonb, %s, %s
                )
                """,
                (
                    _uuid(authorization_id),
                    revocation_id,
                    subject_type,
                    subject_id,
                    envelope.key_id,
                    _claim_text(claims, "jti"),
                    json.dumps(claims, sort_keys=True),
                    envelope.signature,
                    revoked_at,
                ),
            )
        except (OwnerDenied, OwnerDependencyUnavailable):
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("signed D10 revocation persistence failed") from error
        finally:
            cursor.close()

    def _require_transaction(self) -> None:
        if (
            self.connection.closed
            or self.connection.autocommit
            or self.connection.get_transaction_status() != TRANSACTION_STATUS_INTRANS
        ):
            raise OwnerDependencyUnavailable(
                "D10 persistence requires an active PostgreSQL transaction"
            )

    def _is_revoked(
        self, subject_type: str, subject_id: str, authorization_id: str | None
    ) -> bool:
        if authorization_id is None:
            raise OwnerDenied("authorization scope is required for D10 revocation lookup")
        cursor = self._cursor()
        try:
            cursor.execute(
                "SELECT public.g08_d10_gateway_is_revoked(%s::uuid, %s, %s)",
                (_uuid(authorization_id), subject_type, subject_id),
            )
            row = cursor.fetchone()
        except psycopg2.Error as error:
            if error.pgcode == "42501":
                raise OwnerDenied("D10 revocation lookup is outside authorization scope") from error
            raise OwnerDependencyUnavailable("D10 revocation status is unavailable") from error
        finally:
            cursor.close()
        if row is None:
            raise OwnerDependencyUnavailable("D10 revocation status is unavailable")
        return bool(row[0])

    def assert_current_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        authorization_id: str,
        version: str,
        approval_ids: tuple[str, ...],
        decision_time,
        operator_evidence_jti: str | None = None,
        scope: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(transaction, PostgresG08UnitOfWork):
            raise OwnerDependencyUnavailable("PostgreSQL owner transaction is required")
        if transaction.connection is not self.connection or not transaction.active:
            raise OwnerDependencyUnavailable("D10 revalidation must share the owner transaction")
        if scope is None:
            raise OwnerDenied("transactional D10 revalidation requires verified operation scope")
        required_scope = (
            "operation_id",
            "tenant_id",
            "organization_id",
            "action",
            "target_resource",
            "requester_uid",
            "operator_uid",
        )
        if any(
            not isinstance(scope.get(field), str) or not scope[field]
            for field in required_scope
        ):
            raise OwnerDenied("transactional D10 revalidation scope is incomplete")
        if not operator_evidence_jti:
            raise OwnerDenied("operator evidence JTI is required for transactional revalidation")
        cursor = transaction.cursor
        try:
            cursor.execute(
                """
                SELECT public.g08_d10_gateway_assert_current(
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s,
                    %s::uuid, %s::uuid, %s, %s::text[], %s, %s, %s
                )
                """,
                (
                    _uuid(authorization_id),
                    _uuid(scope["operation_id"]),
                    _uuid(scope["tenant_id"]),
                    _uuid(scope["organization_id"]),
                    scope["action"],
                    scope["target_resource"],
                    version,
                    _uuid(scope["requester_uid"]),
                    _uuid(scope["operator_uid"]),
                    operator_evidence_jti,
                    list(approval_ids),
                    scope.get("fence_jti"),
                    scope.get("fence_generation"),
                    decision_time,
                ),
            )
        except (OwnerDenied, OwnerDependencyUnavailable):
            raise
        except psycopg2.Error as error:
            if error.pgcode in {"P0002", "42501", "23505", "23514"}:
                raise OwnerDenied("transactional D10 authority check failed") from error
            raise OwnerDependencyUnavailable(
                "transactional D10 policy and revocation revalidation failed"
            ) from error


class PostgresFenceGenerationStore:
    """Validates and locks the authoritative fencing generation in the caller transaction."""

    def advance_generation_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        scope: Mapping[str, str],
        envelope: SignedEnvelope,
        verifier: SignedEvidenceVerifier,
        decision_time,
    ) -> int:
        if not isinstance(transaction, PostgresG08UnitOfWork) or not transaction.active:
            raise OwnerDependencyUnavailable(
                "fencing-generation update requires an active PostgreSQL transaction"
            )
        claims = verifier.verify_subject_bound(envelope, decision_time)
        for field in (
            "jti", "authorization_id", "operation_id", "tenant_id",
            "organization_id", "action", "target_resource",
        ):
            _claim_text(claims, field)
        if any(claims[field] != expected for field, expected in scope.items()):
            raise OwnerDenied("fencing token scope mismatch")
        generation = claims.get("generation")
        if type(generation) is not int or generation < 1:
            raise OwnerDenied("invalid fencing generation")
        cursor = transaction.cursor
        try:
            cursor.execute(
                """
                SELECT public.g08_d10_gateway_advance_fence(
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s
                )
                """,
                (
                    _uuid(scope["authorization_id"]),
                    _uuid(scope["operation_id"]),
                    _uuid(scope["tenant_id"]),
                    _uuid(scope["organization_id"]),
                    scope["action"],
                    scope["target_resource"],
                    str(claims["jti"]),
                    generation,
                ),
            )
            advanced = cursor.fetchone()
            if advanced is None or int(advanced[0]) != generation:
                raise OwnerDependencyUnavailable("fencing generation did not persist")
        except (OwnerDenied, OwnerDependencyUnavailable):
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("fencing generation update failed") from error
        return generation

    def is_fencing_token_revoked_in_transaction(
        self,
        transaction: OwnerUnitOfWork,
        scope: Mapping[str, str],
        evidence_jti: str,
    ) -> bool:
        if not isinstance(transaction, PostgresG08UnitOfWork) or not transaction.active:
            raise OwnerDependencyUnavailable(
                "fencing revocation check requires an active PostgreSQL transaction"
            )
        try:
            transaction.cursor.execute(
                "SELECT public.g08_d10_gateway_is_revoked(%s::uuid, 'FENCING_TOKEN', %s)",
                (_uuid(scope["authorization_id"]), evidence_jti),
            )
            row = transaction.cursor.fetchone()
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable(
                "fencing-token revocation status is unavailable"
            ) from error
        if row is None:
            raise OwnerDependencyUnavailable("fencing-token revocation status is unavailable")
        return bool(row[0])

    def current_generation_in_transaction(
        self, transaction: OwnerUnitOfWork,         scope: Mapping[str, str],
    ) -> int:
        if not isinstance(transaction, PostgresG08UnitOfWork) or not transaction.active:
            raise OwnerDependencyUnavailable(
                "fencing check requires an active PostgreSQL transaction"
            )
        try:
            transaction.cursor.execute(
                """
                SELECT public.g08_d10_gateway_current_fence(
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s
                )
                """,
                (
                    _uuid(scope["authorization_id"]),
                    _uuid(scope["operation_id"]),
                    _uuid(scope["tenant_id"]),
                    _uuid(scope["organization_id"]),
                    scope["action"],
                    scope["target_resource"],
                ),
            )
            row = transaction.cursor.fetchone()
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("fencing generation is unavailable") from error
        if row is None:
            raise OwnerDenied("fencing scope is not registered")
        return int(row[0])


class CanonicalOwnerPersistence(Protocol):
    """Reviewed canonical SQL gateway required to load and stage owner records."""

    def acquire_global_lock(self, cursor: Any) -> None: ...
    def decision_time(self, cursor: Any): ...
    def load(self, cursor: Any, operation_id: str) -> OwnerSnapshot | None: ...
    def stage_authorization(self, cursor: Any, authorization: Authorization) -> str: ...
    def stage_admission(
        self, cursor: Any, authorization: Authorization,
        entry: StatusEntry, operator: OperatorAssertion,
    ) -> str: ...
    def stage_status(
        self, cursor: Any, authorization: Authorization,
        entry: StatusEntry, operator: OperatorAssertion,
    ) -> str: ...
    def stage_execution(
        self, cursor: Any, authorization: Authorization,
        request: ExecutionRequest, operator: OperatorAssertion,
        evidence: ExecutionEvidence,
    ) -> OwnerReceipt: ...
    def read_receipt(
        self,
        cursor: Any,
        authorization_id: str,
        operation_id: str,
        operator: OperatorAssertion,
    ) -> OwnerReceipt | None: ...


class PostgresG08UnitOfWork:
    """One explicit READ COMMITTED PostgreSQL transaction around canonical SQL callbacks.

    A gateway is mandatory; direct table writes are intentionally not implemented.
    No gateway implementing the missing canonical trusted owner writer currently exists.
    """

    def __init__(self, connection: Any, persistence: CanonicalOwnerPersistence) -> None:
        if (
            connection is None
            or getattr(connection, "closed", True)
            or getattr(connection, "autocommit", True) is not False
            or not callable(getattr(connection, "get_transaction_status", None))
            or not callable(getattr(connection, "set_session", None))
            or connection.get_transaction_status() != 0
        ):
            raise ProtectedWorkflowUnavailable("an idle explicit PostgreSQL connection is required")
        if persistence is None:
            raise OwnerDependencyUnavailable(
                "canonical G08 owner persistence gateway is unavailable"
            )
        required = (
            "acquire_global_lock",
            "decision_time",
            "load",
            "stage_authorization",
            "stage_admission",
            "stage_status",
            "stage_execution",
            "read_receipt",
        )
        if any(not callable(getattr(persistence, method, None)) for method in required):
            raise OwnerDependencyUnavailable(
                "canonical G08 owner persistence gateway is incomplete"
            )
        self.connection = connection
        self.persistence = persistence
        self.cursor = None
        self.active = False
        self.session_user = ""

    def begin_read_committed(self) -> None:
        try:
            self.connection.set_session(isolation_level="READ COMMITTED", autocommit=False)
            self.cursor = self.connection.cursor()
            self.cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            self.cursor.execute("SELECT session_user::text")
            row = self.cursor.fetchone()
        except psycopg2.Error as error:
            self.connection.rollback()
            raise OwnerDependencyUnavailable("cannot begin G08 owner transaction") from error
        if row is None or not row[0]:
            self.connection.rollback()
            raise OwnerDependencyUnavailable("PostgreSQL session identity is unavailable")
        self.session_user = str(row[0])
        self.active = True

    def _require_active(self) -> None:
        if not self.active or self.cursor is None:
            raise OwnerDependencyUnavailable("active G08 PostgreSQL transaction is required")

    def acquire_global_lock(self) -> None:
        self._require_active()
        try:
            self.persistence.acquire_global_lock(self.cursor)
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("canonical G08 history lock/check failed") from error

    def load(self, operation_id: str) -> OwnerSnapshot | None:
        self._require_active()
        try:
            return self.persistence.load(self.cursor, operation_id)
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("canonical G08 owner record read failed") from error

    def decision_time(self):
        self._require_active()
        try:
            value = self.persistence.decision_time(self.cursor)
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("PostgreSQL decision time is unavailable") from error
        if value is None:
            raise OwnerDependencyUnavailable("PostgreSQL decision time is unavailable")
        return value

    def stage_admission(self, authorization, entry, operator) -> str:
        self._require_active()
        try:
            return self.persistence.stage_admission(
                self.cursor, authorization, entry, operator
            )
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("canonical G08 admission staging failed") from error

    def stage_authorization(self, authorization: Authorization) -> str:
        self._require_active()
        try:
            return self.persistence.stage_authorization(self.cursor, authorization)
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable(
                "canonical G08 authorization bootstrap failed"
            ) from error

    def stage_status(self, authorization, entry, operator) -> str:
        self._require_active()
        try:
            return self.persistence.stage_status(self.cursor, authorization, entry, operator)
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("canonical G08 status staging failed") from error

    def stage_execution(self, authorization, request, operator, evidence) -> OwnerReceipt:
        self._require_active()
        try:
            return self.persistence.stage_execution(
                self.cursor, authorization, request, operator, evidence
            )
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("canonical G08 execution staging failed") from error

    def read_receipt(
        self,
        authorization_id: str,
        operation_id: str,
        operator: OperatorAssertion,
    ) -> OwnerReceipt | None:
        self._require_active()
        try:
            return self.persistence.read_receipt(
                self.cursor, authorization_id, operation_id, operator
            )
        except OwnerDenied:
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("canonical G08 receipt read failed") from error

    def commit(self) -> None:
        self._require_active()
        try:
            self.connection.commit()
        finally:
            self.active = False
            self.cursor.close()

    def rollback(self) -> None:
        if self.cursor is None:
            return
        try:
            self.connection.rollback()
        finally:
            self.active = False
            self.cursor.close()

    def bootstrap_and_admit(
        self,
        coordinator: OwnerAuthorizationCoordinator,
        authorization: Authorization,
        context: Any,
        status_id: str,
        policy_envelope: SignedEnvelope,
        approval_envelopes: tuple[SignedEnvelope, ...],
        policy_verifier: SignedEvidenceVerifier,
        approval_verifier: SignedEvidenceVerifier,
    ) -> DurableReceipt:
        if not callable(getattr(self.persistence, "stage_authorization", None)):
            raise OwnerDependencyUnavailable(
                "canonical D10 admission bootstrap adapter is unavailable"
            )
        authority = PostgresG08PolicyAuthority(self.connection)

        def operation():
            self.acquire_global_lock()
            self.stage_authorization(authorization)
            decision_time = self.decision_time()
            authority.append_policy(
                authorization.authorization_id,
                str(authorization.policy_version),
                policy_envelope,
                policy_verifier,
                decision_time,
            )
            for envelope in approval_envelopes:
                authority.append_approval(
                    authorization.authorization_id,
                    str(authorization.policy_version),
                    envelope,
                    policy_verifier,
                    approval_verifier,
                    decision_time,
                )
            return coordinator.admit_in_transaction(
                self, authorization, context, status_id, history_locked=True
            )

        return execute_once(self, operation)


class PostgresG08ReceiptReader:
    """Read-only tenant projection using the signed current D10 reader entitlement."""

    def __init__(
        self,
        *,
        application_sessions: ApplicationSessionVerifier,
        policy_authority: PostgresG08PolicyAuthority,
        policy_verifier: SignedEvidenceVerifier,
    ) -> None:
        if (
            application_sessions is None
            or policy_authority is None
            or policy_verifier is None
        ):
            raise OwnerDependencyUnavailable("tenant receipt projection providers are required")
        self.application_sessions = application_sessions
        self.policy_authority = policy_authority
        self.policy_verifier = policy_verifier

    def read(
        self,
        transaction: PostgresG08UnitOfWork,
        session: SignedEnvelope,
        authorization_id: str,
        operation_id: str,
        policy_version: str,
        decision_time,
    ) -> dict[str, Any]:
        if not transaction.active or transaction.connection is not self.policy_authority.connection:
            raise OwnerDependencyUnavailable(
                "receipt projection requires the shared active transaction"
            )
        app = self.application_sessions.verify(session, decision_time)
        cursor = transaction.cursor
        try:
            tenant_id = str(app.get("tenant_id") or "")
            organization_id = str(app.get("organization_id") or "")
            current_version = self.policy_authority.current_version(
                authorization_id, operation_id, tenant_id, organization_id
            )
            if current_version != policy_version:
                raise OwnerDenied("receipt projection policy is stale")
            policy = self.policy_verifier.verify(
                self.policy_authority.policy(
                    authorization_id,
                    policy_version,
                    operation_id,
                    tenant_id,
                    organization_id,
                ),
                decision_time,
            )
            from services.g08_trust_contract import _string_set, _timestamp

            if not (
                _timestamp(policy, "not_before")
                <= decision_time
                < _timestamp(policy, "expires_at")
            ):
                raise OwnerDenied("receipt projection policy is not currently valid")
            reader_uids = _string_set(policy, "receipt_reader_uids")
            if (
                not tenant_id
                or organization_id != tenant_id
                or tenant_id != policy.get("tenant_id")
                or organization_id != policy.get("organization_id")
                or str(app.get("sub")) not in reader_uids
                or policy.get("authorization_id") != authorization_id
                or policy.get("operation_id") != operation_id
                or policy.get("version") != policy_version
            ):
                raise OwnerDenied("receipt is outside the authorized tenant projection")
            cursor.execute(
                """
                SELECT public.g08_gateway_read_owner_receipt(
                    %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid
                )
                """,
                (
                    _uuid(authorization_id),
                    _uuid(operation_id),
                    _uuid(tenant_id),
                    _uuid(organization_id),
                    policy_version,
                    _uuid(str(app.get("sub") or "")),
                ),
            )
            row = cursor.fetchone()
        except (OwnerDenied, OwnerDependencyUnavailable):
            raise
        except psycopg2.Error as error:
            raise OwnerDependencyUnavailable("tenant-scoped G08 receipt read failed") from error
        if row is None:
            raise OwnerDenied("receipt is outside the authorized tenant projection")
        if row is None or row[0] is None:
            raise OwnerDenied("receipt is outside the authorized tenant projection")
        projection = _json_object(row[0])
        event_id = str(projection["event_id"])
        result = _json_object(projection["result"])
        if result.get("event_id") != event_id:
            raise OwnerDenied("receipt integrity check failed")
        return {
            "authorization_id": authorization_id,
            "operation_id": operation_id,
            "event_id": event_id,
            "result": result,
            "decision_time": str(
                projection.get("decision_time", projection["occurred_at"])
            ),
        }


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as error:
            raise OwnerDependencyUnavailable(
                "persisted G08 signed claims or result are invalid"
            ) from error
    if not isinstance(value, dict):
        raise OwnerDependencyUnavailable("persisted G08 signed claims or result are invalid")
    return value


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise OwnerDenied("invalid UUID in G08 authority scope") from error


def _claim_text(claims: dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value.strip():
        raise OwnerDenied(f"signed G08 evidence is missing {name}")
    return value


def _claim_datetime(claims: dict[str, Any], name: str):
    from datetime import datetime

    value = claims.get(name)
    if not isinstance(value, str):
        raise OwnerDenied(f"signed G08 evidence has invalid {name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OwnerDenied(f"signed G08 evidence has invalid {name}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OwnerDenied(f"signed G08 evidence has timezone-free {name}")
    return parsed
