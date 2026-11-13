"""PostgreSQL adapter for the authenticated ACT-009 customer workflow."""

from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import contextmanager
from typing import Any, Iterator, Mapping
from uuid import uuid4

import psycopg2

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.customer_workflow_service import (
    CustomerWorkflowError,
    CustomerWorkflowEvent,
    SQLiteCustomerWorkflowRepository,
    _approval_from_dict,
    _approval_to_dict,
)
from services.v1_approval_authority import transition_approval_request

_EVENT_COLUMNS = """
    event_id, event_type, organization_id, tenant_id, workspace_id, actor_id,
    idempotency_key, payload_fingerprint, payload_ciphertext, occurred_at
"""


class PostgresCustomerWorkflowRepository(SQLiteCustomerWorkflowRepository):
    """Append-only ACT-009 repository with tenant RLS and transactional evidence."""

    stores_evidence_in_database = True

    def __init__(
        self,
        dsn: str,
        *,
        key: str | bytes,
        connection_factory=None,
    ) -> None:
        material = key.encode("ascii") if isinstance(key, str) else key
        if not material:
            raise CustomerWorkflowError("NEXORA_CUSTOMER_WORKFLOW_KEY is required")
        try:
            self._cipher = self._fernet(material)
        except (TypeError, ValueError) as exc:
            raise CustomerWorkflowError(
                "NEXORA_CUSTOMER_WORKFLOW_KEY is invalid"
            ) from exc
        self.database = dsn
        self.connection_factory = connection_factory or (
            lambda: psycopg2.connect(dsn, connect_timeout=5)
        )

    @staticmethod
    def _fernet(material: bytes):
        from cryptography.fernet import Fernet

        return Fernet(material)

    @contextmanager
    def _connection(self, context: AuthenticatedTenantContext) -> Iterator[Any]:
        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("verified authenticated tenant context is required")
        if context.organization_id != context.tenant_id:
            raise PermissionError("customer workflow tenant scope is invalid")
        if not context.auth_access_token:
            raise PermissionError("verified authentication token is required")
        try:
            connection = self.connection_factory()
        except psycopg2.OperationalError as exc:
            raise CustomerWorkflowError(
                "PostgreSQL customer workflow storage is unavailable"
            ) from exc
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            set_config('nexora.organization_id', %s, true),
                            set_config('nexora.tenant_id', %s, true),
                            set_config('nexora.actor_id', %s, true),
                            set_config('nexora.role', %s, true),
                            set_config('nexora.access_token', %s, true)
                        """,
                        (
                            context.organization_id,
                            context.tenant_id,
                            context.user_id,
                            context.role,
                            context.auth_access_token,
                        ),
                    )
                    cursor.execute(
                        "SELECT nexora_customer_workflow.verified_scope()"
                    )
                    if cursor.fetchone() != (True,):
                        raise PermissionError(
                            "verified customer workflow identity is not authorized"
                        )
                yield connection
        except psycopg2.errors.InsufficientPrivilege as exc:
            raise PermissionError("customer workflow database authorization denied") from exc
        except psycopg2.OperationalError as exc:
            raise CustomerWorkflowError(
                "PostgreSQL customer workflow storage is unavailable"
            ) from exc
        except psycopg2.Error as exc:
            raise CustomerWorkflowError(
                "PostgreSQL customer workflow transaction failed"
            ) from exc
        finally:
            connection.close()

    def append(
        self,
        *,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        event_type: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
    ) -> CustomerWorkflowEvent:
        self._validate_event_type(event_type)
        self._validate_payload(payload)
        if not idempotency_key:
            raise CustomerWorkflowError("an idempotency key is required")
        with self._connection(context) as connection:
            return self._append_locked(
                connection,
                context=context,
                workspace_id=workspace_id,
                event_type=event_type,
                idempotency_key=self._idempotency_hash(workspace_id, idempotency_key),
                payload=payload,
            )

    def append_evidence(
        self,
        *,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
        encrypted_source: bytes,
    ) -> CustomerWorkflowEvent:
        self._validate_payload(payload)
        if not encrypted_source:
            raise CustomerWorkflowError("encrypted customer evidence is required")
        if not idempotency_key:
            raise CustomerWorkflowError("an idempotency key is required")
        hashed_key = self._idempotency_hash(workspace_id, idempotency_key)
        with self._connection(context) as connection:
            event = self._append_locked(
                connection,
                context=context,
                workspace_id=workspace_id,
                event_type="EVIDENCE_ADMITTED",
                idempotency_key=hashed_key,
                payload=payload,
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO nexora_customer_workflow.evidence_objects
                        (event_id, organization_id, tenant_id, workspace_id,
                         encrypted_content, ciphertext_sha256)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        event.event_id,
                        context.organization_id,
                        context.tenant_id,
                        workspace_id,
                        psycopg2.Binary(encrypted_source),
                        hashlib.sha256(encrypted_source).hexdigest(),
                    ),
                )
                cursor.execute(
                    """
                    SELECT ciphertext_sha256 FROM
                        nexora_customer_workflow.evidence_objects
                    WHERE event_id = %s AND organization_id = %s
                      AND tenant_id = %s AND workspace_id = %s
                    """,
                    (event.event_id, context.organization_id, context.tenant_id, workspace_id),
                )
                stored = cursor.fetchone()
            if stored is None:
                raise CustomerWorkflowError(
                    "encrypted customer evidence was not persisted"
                )
        return event

    def get_evidence_ciphertext(
        self, context: AuthenticatedTenantContext, event: CustomerWorkflowEvent
    ) -> bytes:
        with self._connection(context) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT encrypted_content, ciphertext_sha256
                    FROM nexora_customer_workflow.evidence_objects
                    WHERE event_id = %s AND organization_id = %s
                      AND tenant_id = %s AND workspace_id = %s
                    """,
                    (
                        event.event_id,
                        context.organization_id,
                        context.tenant_id,
                        event.workspace_id,
                    ),
                )
                row = cursor.fetchone()
        if row is None:
            raise CustomerWorkflowError("encrypted customer evidence is unavailable")
        ciphertext = bytes(row[0])
        if not hmac.compare_digest(hashlib.sha256(ciphertext).hexdigest(), row[1]):
            raise CustomerWorkflowError("encrypted customer evidence failed integrity checks")
        return ciphertext

    def transition_approval(
        self,
        *,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        approval_id: str,
        target: str,
        reason: str,
        escalated_to: str | None,
    ) -> CustomerWorkflowEvent:
        key = self._idempotency_hash(
            workspace_id,
            self._approval_transition_key(
                context, workspace_id, approval_id, target, reason, escalated_to
            ),
        )
        with self._connection(context) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT pg_advisory_xact_lock(
                        hashtextextended(%s, 0)
                    )
                    """,
                    (
                        ":".join(
                            (
                                context.organization_id,
                                context.tenant_id,
                                workspace_id,
                                approval_id,
                            )
                        ),
                    ),
                )
            existing = self._get_by_idempotency(connection, context, key)
            if existing is not None:
                return existing
            events = self._events_locked(connection, context, workspace_id)
            request_event = next(
                (
                    event for event in events
                    if event.event_type == "APPROVAL_REQUESTED"
                    and event.payload.get("approval_id") == approval_id
                ),
                None,
            )
            if request_event is None:
                raise PermissionError("approval is not available in this tenant workspace")
            current_data = dict(request_event.payload["approval"])
            current_data.setdefault("created_at", request_event.occurred_at)
            for event in events:
                if (
                    event.event_type == "APPROVAL_TRANSITIONED"
                    and event.payload.get("approval_id") == approval_id
                ):
                    current_data = dict(event.payload["approval"])
                    current_data.setdefault("created_at", request_event.occurred_at)
            current = _approval_from_dict(current_data)
            expected_role = (
                "executive" if current.current_approver_role == "ceo"
                else current.current_approver_role
            )
            if context.role != expected_role:
                raise PermissionError("the current approval stage is assigned to another role")
            if context.user_id == current.requesting_actor:
                raise PermissionError("the requester cannot approve their own decision")
            if target not in {"APPROVED", "REJECTED", "ESCALATED"}:
                raise CustomerWorkflowError("unsupported customer approval transition")
            if target == "ESCALATED" and escalated_to not in {"cio", "ceo"}:
                raise CustomerWorkflowError("escalation target must be CIO or CEO")
            updated, history = transition_approval_request(
                current,
                to_state=target,
                actor=context.user_id,
                reason=reason,
                actor_role=context.role,
                escalated_to=escalated_to,
            )
            payload = {
                "approval_id": approval_id,
                "approval": _approval_to_dict(updated),
                "history": {
                    "history_id": history.history_id,
                    "request_id": history.request_id,
                    "from_state": history.from_state,
                    "to_state": history.to_state,
                    "actor": history.actor,
                    "actor_role": history.actor_role,
                    "reason": history.reason,
                    "action": history.action,
                    "occurred_at": history.occurred_at.isoformat(),
                },
            }
            return self._append_locked(
                connection,
                context=context,
                workspace_id=workspace_id,
                event_type="APPROVAL_TRANSITIONED",
                idempotency_key=key,
                payload=payload,
            )

    def get_by_idempotency(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        idempotency_key: str,
    ) -> CustomerWorkflowEvent | None:
        with self._connection(context) as connection:
            return self._get_by_idempotency(
                connection,
                context,
                self._idempotency_hash(workspace_id, idempotency_key),
            )

    def get(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        event_id: str,
    ) -> CustomerWorkflowEvent:
        with self._connection(context) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {_EVENT_COLUMNS}
                    FROM nexora_customer_workflow.events
                    WHERE event_id = %s AND organization_id = %s
                      AND tenant_id = %s AND workspace_id = %s
                    """,
                    (event_id, context.organization_id, context.tenant_id, workspace_id),
                )
                row = cursor.fetchone()
        if row is None:
            raise PermissionError("customer workflow record is not available in this tenant")
        return self._event(self._normalize_row(row))

    def list_workspace_events(
        self, context: AuthenticatedTenantContext, workspace_id: str
    ) -> tuple[CustomerWorkflowEvent, ...]:
        with self._connection(context) as connection:
            rows = self._events_locked(connection, context, workspace_id)
        if not rows or not any(event.event_type == "WORKSPACE_CREATED" for event in rows):
            raise PermissionError("customer workspace is not available in this tenant")
        return rows

    def list_workspaces(
        self, context: AuthenticatedTenantContext
    ) -> tuple[CustomerWorkflowEvent, ...]:
        with self._connection(context) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {_EVENT_COLUMNS}
                    FROM nexora_customer_workflow.events
                    WHERE organization_id = %s AND tenant_id = %s
                      AND event_type = 'WORKSPACE_CREATED'
                    ORDER BY occurred_at DESC, event_id
                    """,
                    (context.organization_id, context.tenant_id),
                )
                rows = cursor.fetchall()
        return tuple(self._event(self._normalize_row(row)) for row in rows)

    def _events_locked(
        self,
        connection: Any,
        context: AuthenticatedTenantContext,
        workspace_id: str,
    ) -> tuple[CustomerWorkflowEvent, ...]:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_EVENT_COLUMNS}
                FROM nexora_customer_workflow.events
                WHERE organization_id = %s AND tenant_id = %s AND workspace_id = %s
                ORDER BY occurred_at, event_id
                """,
                (context.organization_id, context.tenant_id, workspace_id),
            )
            rows = cursor.fetchall()
        return tuple(self._event(self._normalize_row(row)) for row in rows)

    def _append_locked(
        self,
        connection: Any,
        *,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        event_type: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
    ) -> CustomerWorkflowEvent:
        self._validate_event_type(event_type)
        self._validate_payload(payload)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_fingerprint = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (
                    ":".join(
                        (
                            context.organization_id,
                            context.tenant_id,
                            idempotency_key,
                        )
                    ),
                ),
            )
        existing = self._get_by_idempotency(connection, context, idempotency_key)
        if existing is not None:
            self._ensure_same_operation(existing, workspace_id, event_type, payload_fingerprint)
            return existing

        event_id = str(uuid4())
        metadata = self._event_metadata(
            connection, context, workspace_id, event_type, payload
        )
        ciphertext = self._cipher.encrypt(payload_json.encode("utf-8")).decode("ascii")
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO nexora_customer_workflow.events (
                    event_id, event_type, organization_id, tenant_id, workspace_id,
                    actor_id, idempotency_key, payload_fingerprint, payload_ciphertext,
                    approval_id, approval_action, approval_state, approval_stage,
                    approval_version, approval_requesting_actor, approval_escalated_to,
                    ask_event_id, decision_event_id, evidence_event_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (organization_id, tenant_id, idempotency_key) DO NOTHING
                RETURNING {_EVENT_COLUMNS}
                """,
                (
                    event_id,
                    event_type,
                    context.organization_id,
                    context.tenant_id,
                    workspace_id,
                    context.user_id,
                    idempotency_key,
                    payload_fingerprint,
                    ciphertext,
                    metadata["approval_id"],
                    metadata["approval_action"],
                    metadata["approval_state"],
                    metadata["approval_stage"],
                    metadata["approval_version"],
                    metadata["approval_requesting_actor"],
                    metadata["approval_escalated_to"],
                    metadata["ask_event_id"],
                    metadata["decision_event_id"],
                    metadata["evidence_event_id"],
                ),
            )
            row = cursor.fetchone()
        if row is None:
            existing = self._get_by_idempotency(connection, context, idempotency_key)
            if existing is None:
                raise CustomerWorkflowError("customer workflow idempotency conflict")
            self._ensure_same_operation(existing, workspace_id, event_type, payload_fingerprint)
            return existing
        return self._event(self._normalize_row(row))

    def _event_metadata(
        self,
        connection: Any,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = {
            "approval_id": None,
            "approval_action": None,
            "approval_state": None,
            "approval_stage": None,
            "approval_version": None,
            "approval_requesting_actor": None,
            "approval_escalated_to": None,
            "ask_event_id": None,
            "decision_event_id": None,
            "evidence_event_id": None,
        }
        if event_type == "ASK_ANSWERED":
            references = payload.get("evidence_references", ())
            if references:
                result["evidence_event_id"] = references[0]["record_id"]
        elif event_type == "DECISION_CREATED":
            result.update(
                ask_event_id=payload["ask_id"],
                evidence_event_id=payload["evidence_id"],
            )
        if event_type == "APPROVAL_REQUESTED":
            approval = payload["approval"]
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ask_event_id FROM nexora_customer_workflow.events
                    WHERE event_id = %s AND organization_id = %s
                      AND tenant_id = %s AND workspace_id = %s
                    """,
                    (
                        payload["decision_id"],
                        context.organization_id,
                        context.tenant_id,
                        workspace_id,
                    ),
                )
                decision_row = cursor.fetchone()
            if decision_row is None:
                raise PermissionError("decision is not available in this tenant workspace")
            result.update(
                approval_id=payload["approval_id"],
                approval_state=approval["state"],
                approval_stage=approval["workflow_stage"],
                approval_version=1,
                approval_requesting_actor=approval["requesting_actor"],
                ask_event_id=decision_row[0],
                decision_event_id=payload["decision_id"],
                evidence_event_id=payload["evidence_id"],
            )
        elif event_type == "APPROVAL_TRANSITIONED":
            approval = payload["approval"]
            result.update(
                approval_id=payload["approval_id"],
                approval_action=(
                    "APPROVED"
                    if approval["state"] == "PENDING"
                    else approval["state"]
                ),
                approval_state=approval["state"],
                approval_stage=approval["workflow_stage"],
                approval_requesting_actor=approval["requesting_actor"],
                approval_escalated_to=approval.get("escalated_to"),
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT version FROM nexora_customer_workflow.approvals
                    WHERE approval_id = %s AND organization_id = %s
                      AND tenant_id = %s AND workspace_id = %s
                    """,
                    (
                        result["approval_id"],
                        context.organization_id,
                        context.tenant_id,
                        workspace_id,
                    ),
                )
                row = cursor.fetchone()
            if row is None:
                raise PermissionError("approval is not available in this tenant workspace")
            result["approval_version"] = row[0] + 1
        elif event_type == "EVIDENCE_EXPORT_CREATED":
            package = payload["package"]
            result.update(
                approval_id=package["approval"]["request_id"],
                ask_event_id=package["ask"]["record_id"],
                decision_event_id=package["decision"]["record_id"],
                evidence_event_id=package["evidence"]["record_id"],
            )
        return result

    def _get_by_idempotency(self, connection, context, idempotency_key):
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_EVENT_COLUMNS}
                FROM nexora_customer_workflow.events
                WHERE organization_id = %s AND tenant_id = %s AND idempotency_key = %s
                """,
                (context.organization_id, context.tenant_id, idempotency_key),
            )
            row = cursor.fetchone()
        return self._event(self._normalize_row(row)) if row else None

    @staticmethod
    def _normalize_row(row):
        values = list(row)
        values[9] = values[9].isoformat()
        return tuple(str(value) if index < 8 else value for index, value in enumerate(values))

    @staticmethod
    def _ensure_same_operation(event, workspace_id, event_type, payload_fingerprint):
        if (
            event.workspace_id != workspace_id
            or event.event_type != event_type
            or event.payload_fingerprint != payload_fingerprint
        ):
            raise CustomerWorkflowError("idempotency key was reused for a different operation")

    @staticmethod
    def _approval_transition_key(context, workspace_id, approval_id, target, reason, escalated_to):
        from universal_evidence.normalization.fingerprints import fingerprint

        return fingerprint(
            "approval-transition", workspace_id, approval_id, context.user_id,
            context.role, target, reason, escalated_to,
        )
