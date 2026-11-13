"""Authenticated customer evidence, decision, approval, and export workflow."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid4, uuid5

from cryptography.fernet import Fernet, InvalidToken

from auth.authenticated_tenant import AuthenticatedTenantContext
from services.prospect_data_intake_service import (
    ProspectAnalysis,
    analyze_upload,
    scan_upload,
)
from services.v1_approval_authority import (
    ApprovalRequest,
    transition_approval_request,
)
from shared.prospect_answers import prospect_evidence_answer
from universal_evidence.normalization.fingerprints import fingerprint
from universal_evidence.persistence import (
    LifecyclePersistenceError,
    run_universal_evidence_migrations,
)
from universal_evidence.pilot.admission import admit_uploaded_evidence

_EVENT_TYPES = frozenset(
    {
        "WORKSPACE_CREATED",
        "EVIDENCE_ADMITTED",
        "ASK_ANSWERED",
        "DECISION_CREATED",
        "APPROVAL_REQUESTED",
        "APPROVAL_TRANSITIONED",
        "EVIDENCE_EXPORT_CREATED",
    }
)
_UPLOAD_ROLES = frozenset({"client_admin", "executive", "cio", "finance", "operations"})
_DECISION_ROLES = _UPLOAD_ROLES
_APPROVER_ROLES = frozenset({"finance", "cio", "executive"})
_SUPPORTED_PROFILES = frozenset(
    {
        "AWS billing/CUR-derived CSV",
        "Azure cost export",
        "GCP billing export",
        "SaaS/license CSV or Excel",
        "Generic technology-cost Excel/CSV",
        "Manual invoice/bill spreadsheet",
    }
)


class CustomerWorkflowError(RuntimeError):
    """A customer workflow request could not be completed safely."""


def _configured_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    path = os.getenv(f"{name}_FILE", "").strip()
    if path:
        try:
            return Path(path).read_text(encoding="ascii").strip()
        except OSError as exc:
            raise CustomerWorkflowError(f"{name}_FILE could not be read") from exc
    return ""


@dataclass(frozen=True, slots=True)
class CustomerWorkflowEvent:
    event_id: str
    event_type: str
    organization_id: str
    tenant_id: str
    workspace_id: str
    actor_id: str
    idempotency_key: str
    payload_fingerprint: str
    payload: Mapping[str, Any]
    occurred_at: str


@dataclass(frozen=True, slots=True)
class _AnalysisTenant:
    tenant_id: str
    audit_id: str
    expires_at: str


class SQLiteCustomerWorkflowRepository:
    """Append-only encrypted event repository sharing ACT-009's database."""

    stores_evidence_in_database = False

    def __init__(
        self,
        database: str | Path,
        *,
        key: str | bytes,
        connection_factory=None,
    ) -> None:
        value = str(database or "").strip()
        if not value:
            raise LifecyclePersistenceError("durable customer workflow database is required")
        if value.lower().startswith(("postgres://", "postgresql://")):
            raise LifecyclePersistenceError(
                "customer workflow events require the configured ACT-009 SQLite database"
            )
        material = key.encode("ascii") if isinstance(key, str) else key
        if not material:
            raise CustomerWorkflowError("NEXORA_CUSTOMER_WORKFLOW_KEY is required")
        try:
            self._cipher = Fernet(material)
        except (TypeError, ValueError) as exc:
            raise CustomerWorkflowError("customer workflow encryption key is invalid") from exc
        self.database = value
        self.connection_factory = connection_factory or (
            lambda: sqlite3.connect(self.database, timeout=15)
        )
        run_universal_evidence_migrations(self.database, connection_factory=self.connection_factory)

    @classmethod
    def from_environment(cls):
        backend = os.getenv("NEXORA_CUSTOMER_WORKFLOW_BACKEND", "").strip().lower()
        environment = os.getenv(
            "ENVIRONMENT", os.getenv("CLOUD_ADVISOR_ENV", "development")
        ).strip().lower()
        key = _configured_secret("NEXORA_CUSTOMER_WORKFLOW_KEY")
        root = os.getenv("NEXORA_CUSTOMER_EVIDENCE_ROOT", "var/customer_evidence").strip()
        if not key:
            raise CustomerWorkflowError(
                "NEXORA_CUSTOMER_WORKFLOW_KEY must be configured outside the repository"
            )
        if backend == "postgres":
            dsn = _configured_secret("NEXORA_CUSTOMER_WORKFLOW_DSN")
            if not dsn:
                raise CustomerWorkflowError(
                    "NEXORA_CUSTOMER_WORKFLOW_DSN must be configured outside the repository"
                )
            from services.postgres_customer_workflow_repository import (
                PostgresCustomerWorkflowRepository,
            )

            return PostgresCustomerWorkflowRepository(dsn, key=key), Path(root)
        if backend == "sqlite":
            if environment not in {"development", "dev", "test", "local"}:
                raise CustomerWorkflowError(
                    "SQLite customer workflow storage is restricted to development and tests"
                )
            database = os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB", "").strip()
            if not database:
                raise CustomerWorkflowError("NEXORA_UNIVERSAL_EVIDENCE_DB is required")
            return cls(database, key=key), Path(root)
        raise CustomerWorkflowError(
            "NEXORA_CUSTOMER_WORKFLOW_BACKEND must explicitly select "
            "postgres or development-only sqlite"
        )

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
        connection = self.connection_factory()
        try:
            connection.execute("PRAGMA busy_timeout = 15000")
            connection.execute("BEGIN IMMEDIATE")
            record = self._append_locked(
                connection,
                context=context,
                workspace_id=workspace_id,
                event_type=event_type,
                idempotency_key=self._idempotency_hash(workspace_id, idempotency_key),
                payload=payload,
            )
            connection.commit()
            return record
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def append_evidence(
        self,
        *,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
        encrypted_source: bytes,
    ) -> CustomerWorkflowEvent:
        raise CustomerWorkflowError(
            "database-backed evidence storage is unavailable for the SQLite adapter"
        )

    def get_evidence_ciphertext(
        self, context: AuthenticatedTenantContext, event: CustomerWorkflowEvent
    ) -> bytes:
        raise CustomerWorkflowError(
            "database-backed evidence storage is unavailable for the SQLite adapter"
        )

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
        key = fingerprint(
            "approval-transition", workspace_id, approval_id, context.user_id,
            context.role, target, reason, escalated_to,
        )
        hashed_key = self._idempotency_hash(workspace_id, key)
        connection = self.connection_factory()
        try:
            connection.execute("PRAGMA busy_timeout = 15000")
            connection.execute("BEGIN IMMEDIATE")
            existing = self._get_by_idempotency(connection, context, hashed_key)
            if existing is not None:
                connection.commit()
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
            record = self._append_locked(
                connection,
                context=context,
                workspace_id=workspace_id,
                event_type="APPROVAL_TRANSITIONED",
                idempotency_key=hashed_key,
                payload=payload,
            )
            connection.commit()
            return record
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_by_idempotency(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        idempotency_key: str,
    ) -> CustomerWorkflowEvent | None:
        connection = self.connection_factory()
        try:
            row = self._get_by_idempotency(
                connection,
                context,
                self._idempotency_hash(workspace_id, idempotency_key),
            )
        finally:
            connection.close()
        return row

    def get(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        event_id: str,
    ) -> CustomerWorkflowEvent:
        connection = self.connection_factory()
        try:
            row = connection.execute(
                """SELECT event_id, event_type, organization_id, tenant_id, workspace_id,
                          actor_id, idempotency_key, payload_fingerprint,
                          payload_ciphertext, occurred_at
                   FROM customer_workflow_events
                   WHERE event_id=? AND organization_id=? AND tenant_id=? AND workspace_id=?""",
                (event_id, context.organization_id, context.tenant_id, workspace_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise PermissionError("customer workflow record is not available in this tenant")
        return self._event(row)

    def list_workspace_events(
        self, context: AuthenticatedTenantContext, workspace_id: str
    ) -> tuple[CustomerWorkflowEvent, ...]:
        connection = self.connection_factory()
        try:
            rows = connection.execute(
                """SELECT event_id, event_type, organization_id, tenant_id, workspace_id,
                          actor_id, idempotency_key, payload_fingerprint,
                          payload_ciphertext, occurred_at
                   FROM customer_workflow_events
                   WHERE organization_id=? AND tenant_id=? AND workspace_id=?
                   ORDER BY occurred_at, event_id""",
                (context.organization_id, context.tenant_id, workspace_id),
            ).fetchall()
        finally:
            connection.close()
        events = tuple(self._event(row) for row in rows)
        if not events or not any(event.event_type == "WORKSPACE_CREATED" for event in events):
            raise PermissionError("customer workspace is not available in this tenant")
        return events

    def list_workspaces(
        self, context: AuthenticatedTenantContext
    ) -> tuple[CustomerWorkflowEvent, ...]:
        connection = self.connection_factory()
        try:
            rows = connection.execute(
                """SELECT event_id, event_type, organization_id, tenant_id, workspace_id,
                          actor_id, idempotency_key, payload_fingerprint,
                          payload_ciphertext, occurred_at
                   FROM customer_workflow_events
                   WHERE organization_id=? AND tenant_id=? AND event_type='WORKSPACE_CREATED'
                   ORDER BY occurred_at DESC, event_id""",
                (context.organization_id, context.tenant_id),
            ).fetchall()
        finally:
            connection.close()
        return tuple(self._event(row) for row in rows)

    def _events_locked(
        self,
        connection: sqlite3.Connection,
        context: AuthenticatedTenantContext,
        workspace_id: str,
    ) -> tuple[CustomerWorkflowEvent, ...]:
        rows = connection.execute(
            """SELECT event_id, event_type, organization_id, tenant_id, workspace_id,
                      actor_id, idempotency_key, payload_fingerprint,
                      payload_ciphertext, occurred_at
               FROM customer_workflow_events
               WHERE organization_id=? AND tenant_id=? AND workspace_id=?
               ORDER BY occurred_at, event_id""",
            (context.organization_id, context.tenant_id, workspace_id),
        ).fetchall()
        return tuple(self._event(row) for row in rows)

    def _append_locked(
        self,
        connection: sqlite3.Connection,
        *,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        event_type: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
    ) -> CustomerWorkflowEvent:
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_fingerprint = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        existing = self._get_by_idempotency(connection, context, idempotency_key)
        if existing is not None:
            if (
                existing.workspace_id != workspace_id
                or existing.event_type != event_type
                or existing.payload_fingerprint != payload_fingerprint
            ):
                raise CustomerWorkflowError("idempotency key was reused for a different operation")
            return existing
        event_id = str(uuid4())
        occurred_at = datetime.now(timezone.utc).isoformat()
        encrypted = self._cipher.encrypt(payload_json.encode("utf-8")).decode("ascii")
        connection.execute(
            """INSERT INTO customer_workflow_events
               (event_id, event_type, organization_id, tenant_id, workspace_id, actor_id,
                idempotency_key, payload_fingerprint, payload_ciphertext, occurred_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                event_type,
                context.organization_id,
                context.tenant_id,
                workspace_id,
                context.user_id,
                idempotency_key,
                payload_fingerprint,
                encrypted,
                occurred_at,
            ),
        )
        return CustomerWorkflowEvent(
            event_id,
            event_type,
            context.organization_id,
            context.tenant_id,
            workspace_id,
            context.user_id,
            idempotency_key,
            payload_fingerprint,
            dict(payload),
            occurred_at,
        )

    def _get_by_idempotency(self, connection, context, idempotency_key):
        row = connection.execute(
            """SELECT event_id, event_type, organization_id, tenant_id, workspace_id,
                      actor_id, idempotency_key, payload_fingerprint,
                      payload_ciphertext, occurred_at
               FROM customer_workflow_events
               WHERE organization_id=? AND tenant_id=? AND idempotency_key=?""",
            (context.organization_id, context.tenant_id, idempotency_key),
        ).fetchone()
        return self._event(row) if row else None

    def _event(self, row) -> CustomerWorkflowEvent:
        try:
            plaintext = self._cipher.decrypt(row[8].encode("ascii"))
            payload = json.loads(plaintext)
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CustomerWorkflowError("customer workflow record failed integrity checks") from exc
        expected_fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if not hmac.compare_digest(expected_fingerprint, row[7]):
            raise CustomerWorkflowError("customer workflow record failed integrity checks")
        return CustomerWorkflowEvent(
            row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], payload, row[9]
        )

    @staticmethod
    def _idempotency_hash(workspace_id: str, key: str) -> str:
        return hashlib.sha256(f"{workspace_id}\0{key}".encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_event_type(event_type: str) -> None:
        if event_type not in _EVENT_TYPES:
            raise CustomerWorkflowError("unsupported customer workflow event")

    @staticmethod
    def _validate_payload(payload: Mapping[str, Any]) -> None:
        try:
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise CustomerWorkflowError("customer workflow payload is not serializable") from exc


class CustomerWorkflowService:
    """Orchestrate the customer journey on verified tenant context and ACT-009 storage."""

    def __init__(
        self,
        repository: SQLiteCustomerWorkflowRepository,
        *,
        evidence_root: str | Path,
        evidence_key: str | bytes,
    ) -> None:
        self.repository = repository
        material = evidence_key.encode("ascii") if isinstance(evidence_key, str) else evidence_key
        try:
            self._evidence_cipher = Fernet(material)
        except (TypeError, ValueError) as exc:
            raise CustomerWorkflowError("customer evidence encryption key is invalid") from exc
        self.evidence_root = Path(evidence_root).resolve()

    @classmethod
    def from_environment(cls):
        evidence_key = _configured_secret("NEXORA_CUSTOMER_EVIDENCE_KEY")
        if not evidence_key:
            raise CustomerWorkflowError(
                "NEXORA_CUSTOMER_EVIDENCE_KEY must be configured outside the repository"
            )
        repository, root = SQLiteCustomerWorkflowRepository.from_environment()
        return cls(repository, evidence_root=root, evidence_key=evidence_key)

    def create_workspace(
        self,
        context: AuthenticatedTenantContext,
        *,
        name: str,
        operation_id: str | None = None,
    ) -> CustomerWorkflowEvent:
        self._context(context)
        if context.role not in _UPLOAD_ROLES:
            raise PermissionError("this tenant role cannot create a customer workspace")
        normalized = " ".join(str(name or "").split())
        if not normalized or len(normalized) > 120:
            raise CustomerWorkflowError("workspace name must contain 1 to 120 characters")
        operation_id = str(operation_id or uuid4())
        workspace_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{context.organization_id}:{context.user_id}:{operation_id}",
            )
        )
        return self.repository.append(
            context=context,
            workspace_id=workspace_id,
            event_type="WORKSPACE_CREATED",
            idempotency_key=f"workspace:{operation_id}",
            payload={"name": normalized, "created_by": context.user_id},
        )

    def list_workspaces(self, context: AuthenticatedTenantContext):
        self._context(context)
        return self.repository.list_workspaces(context)

    def upload_evidence(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        *,
        filename: str,
        content: bytes,
        input_profile: str,
    ) -> CustomerWorkflowEvent:
        self._require_workspace(context, workspace_id)
        if context.role not in _UPLOAD_ROLES:
            raise PermissionError("this tenant role cannot upload customer evidence")
        if Path(filename).suffix.lower() not in {".csv", ".xlsx"}:
            raise CustomerWorkflowError("customer workspace accepts validated CSV or XLSX evidence")
        if input_profile not in _SUPPORTED_PROFILES:
            raise CustomerWorkflowError("unsupported customer evidence input profile")
        scan = scan_upload(filename, content)
        idempotency_key = f"evidence:{workspace_id}:{scan['sha256']}"
        existing = self.repository.get_by_idempotency(context, workspace_id, idempotency_key)
        if existing is not None:
            if (
                existing.event_type != "EVIDENCE_ADMITTED"
                or existing.payload.get("source_sha256") != scan["sha256"]
            ):
                raise CustomerWorkflowError(
                    "evidence idempotency key conflicts with an existing record"
                )
            return existing
        now = datetime.now(timezone.utc)
        analysis_tenant = _AnalysisTenant(
            context.tenant_id,
            workspace_id,
            (now + timedelta(days=90)).isoformat(),
        )
        admission = admit_uploaded_evidence(
            analysis_tenant,
            filename=filename,
            content=content,
            now=now,
            tenant_context=context,
        )
        analysis = analyze_upload(
            analysis_tenant,
            profile=input_profile,
            filename=filename,
            content=content,
        )
        evidence_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{context.organization_id}:{context.tenant_id}:{workspace_id}:{scan['sha256']}",
            )
        )
        database_evidence = self.repository.stores_evidence_in_database
        if database_evidence:
            encrypted_source = self._evidence_cipher.encrypt(bytes(content))
            source_reference = "postgresql:nexora_customer_workflow.evidence_objects"
        else:
            relative_path = Path(context.organization_id) / context.tenant_id / workspace_id / (
                evidence_id + ".enc"
            )
            destination = (self.evidence_root / relative_path).resolve()
            if not destination.is_relative_to(self.evidence_root):
                raise CustomerWorkflowError("customer evidence path is outside the configured root")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + f".{uuid4()}.tmp")
            encrypted_source = self._evidence_cipher.encrypt(bytes(content))
            temporary.write_bytes(encrypted_source)
            temporary.replace(destination)
            source_reference = relative_path.as_posix()
        payload = {
            "evidence_id": evidence_id,
            "filename": Path(filename).name,
            "input_profile": input_profile,
            "source_sha256": scan["sha256"],
            "source_size": scan["size"],
            "scanner": scan["scanner"],
            "validation_status": scan["status"],
            "admission_fingerprint": admission.fingerprint,
            "evidence_fingerprint": admission.evidence_fingerprint,
            "analysis": _analysis_to_dict(analysis),
            "encrypted_source": source_reference,
        }
        if database_evidence:
            return self.repository.append_evidence(
                context=context,
                workspace_id=workspace_id,
                idempotency_key=idempotency_key,
                payload=payload,
                encrypted_source=encrypted_source,
            )
        try:
            return self.repository.append(
                context=context,
                workspace_id=workspace_id,
                event_type="EVIDENCE_ADMITTED",
                idempotency_key=idempotency_key,
                payload=payload,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            if destination.exists():
                destination.unlink()
            raise

    def ask(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        *,
        evidence_id: str,
        question: str,
    ) -> CustomerWorkflowEvent:
        self._require_workspace(context, workspace_id)
        evidence = self._find_evidence(context, workspace_id, evidence_id)
        normalized_question = " ".join(str(question or "").split())
        if not normalized_question or len(normalized_question) > 1000:
            raise CustomerWorkflowError("question must contain 1 to 1000 characters")
        content = self._load_source(context, evidence)
        tenant = _AnalysisTenant(
            context.tenant_id,
            workspace_id,
            (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
        )
        analysis = analyze_upload(
            tenant,
            profile=str(evidence.payload["input_profile"]),
            filename=str(evidence.payload["filename"]),
            content=content,
        )
        answer = prospect_evidence_answer(
            normalized_question,
            analysis,
            scope_label="Current customer workspace",
        )
        state = "INSUFFICIENT" if answer.startswith("UNKNOWN") else "GROUNDED"
        return self.repository.append(
            context=context,
            workspace_id=workspace_id,
            event_type="ASK_ANSWERED",
            idempotency_key=f"ask:{workspace_id}:{evidence_id}:{context.user_id}:{fingerprint(normalized_question)}",
            payload={
                "evidence_id": evidence_id,
                "question": normalized_question,
                "answer": answer,
                "state": state,
                "evidence_references": [
                    {
                        "record_id": evidence.event_id,
                        "sha256": evidence.payload["source_sha256"],
                        "filename": evidence.payload["filename"],
                    }
                ],
            },
        )

    def create_decision(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        *,
        ask_id: str,
        decision: str,
        rationale: str,
    ) -> CustomerWorkflowEvent:
        self._require_workspace(context, workspace_id)
        if context.role not in _DECISION_ROLES:
            raise PermissionError("this tenant role cannot create customer decisions")
        ask = self._get_typed_event(context, workspace_id, ask_id, "ASK_ANSWERED")
        if ask.payload.get("state") != "GROUNDED":
            raise CustomerWorkflowError("a decision requires an Ask answer grounded in evidence")
        selected_decision = " ".join(str(decision or "").split())
        selected_rationale = " ".join(str(rationale or "").split())
        if not selected_decision or len(selected_decision) > 500:
            raise CustomerWorkflowError("decision must contain 1 to 500 characters")
        if not selected_rationale or len(selected_rationale) > 2000:
            raise CustomerWorkflowError("decision rationale must contain 1 to 2000 characters")
        evidence = self._find_evidence(
            context, workspace_id, str(ask.payload["evidence_id"])
        )
        decision_id = str(
            uuid5(
                NAMESPACE_URL,
                f"{workspace_id}:{ask_id}:{context.user_id}:"
                f"{fingerprint(selected_decision, selected_rationale)}",
            )
        )
        return self.repository.append(
            context=context,
            workspace_id=workspace_id,
            event_type="DECISION_CREATED",
            idempotency_key=(
                f"decision:{workspace_id}:{ask_id}:{context.user_id}:"
                f"{fingerprint(selected_decision, selected_rationale)}"
            ),
            payload={
                "decision_id": decision_id,
                "ask_id": ask_id,
                "evidence_id": evidence.event_id,
                "decision": selected_decision,
                "rationale": selected_rationale,
                "source_references": ask.payload["evidence_references"],
                "created_by": context.user_id,
            },
        )

    def request_approval(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        *,
        decision_id: str,
        reason: str,
    ) -> CustomerWorkflowEvent:
        self._require_workspace(context, workspace_id)
        if context.role not in _DECISION_ROLES:
            raise PermissionError("this tenant role cannot request customer approval")
        decision_event = self._get_typed_event(
            context, workspace_id, decision_id, "DECISION_CREATED", key_field="decision_id"
        )
        decision = decision_event.payload
        approval_id = str(uuid5(NAMESPACE_URL, f"{workspace_id}:{decision['decision_id']}"))
        request = ApprovalRequest(
            request_id=approval_id,
            organization_id=context.organization_id,
            tenant_id=context.tenant_id,
            subject_id=str(decision["decision_id"]),
            requested_action=str(decision["decision"]),
            state="PENDING",
            requesting_actor=context.user_id,
            reason=" ".join(str(reason or "").split()),
            created_at=_timestamp(decision_event.occurred_at),
            workflow_stage="FINANCE",
            current_approver_role="finance",
        )
        if not request.reason or len(request.reason) > 2000:
            raise CustomerWorkflowError("approval reason must contain 1 to 2000 characters")
        existing = self.repository.get_by_idempotency(
            context, workspace_id, f"approval:{workspace_id}:{decision['decision_id']}"
        )
        if existing is not None:
            if existing.event_type != "APPROVAL_REQUESTED":
                raise CustomerWorkflowError(
                    "approval idempotency key conflicts with an existing record"
                )
            if existing.payload["approval"]["reason"] != request.reason:
                raise CustomerWorkflowError(
                    "approval already exists with a different request reason"
                )
            return existing
        evidence = self._find_evidence(
            context, workspace_id, str(decision["evidence_id"])
        )
        return self.repository.append(
            context=context,
            workspace_id=workspace_id,
            event_type="APPROVAL_REQUESTED",
            idempotency_key=f"approval:{workspace_id}:{decision['decision_id']}",
            payload={
                "approval_id": request.request_id,
                "approval": _approval_to_dict(request),
                "decision_id": decision_event.event_id,
                "evidence_id": evidence.event_id,
                "source_references": decision["source_references"],
            },
        )

    def transition_approval(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        *,
        approval_id: str,
        target: str,
        reason: str,
        escalated_to: str | None = None,
    ) -> CustomerWorkflowEvent:
        self._require_workspace(context, workspace_id)
        if context.role not in _APPROVER_ROLES:
            raise PermissionError("this tenant role cannot act as a customer approver")
        normalized_reason = " ".join(str(reason or "").split())
        if not normalized_reason or len(normalized_reason) > 2000:
            raise CustomerWorkflowError("approval reason must contain 1 to 2000 characters")
        return self.repository.transition_approval(
            context=context,
            workspace_id=workspace_id,
            approval_id=approval_id,
            target=target,
            reason=normalized_reason,
            escalated_to=escalated_to,
        )

    def export_evidence(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        *,
        approval_id: str,
    ) -> CustomerWorkflowEvent:
        if context.role not in _UPLOAD_ROLES:
            raise PermissionError("this tenant role cannot export customer evidence")
        events = self._require_workspace(context, workspace_id)
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
        approval = dict(request_event.payload["approval"])
        transitions = [
            event for event in events
            if event.event_type == "APPROVAL_TRANSITIONED"
            and event.payload.get("approval_id") == approval_id
        ]
        if transitions:
            approval = dict(transitions[-1].payload["approval"])
        if approval.get("state") != "APPROVED":
            raise CustomerWorkflowError("evidence export requires a fully approved decision")
        decision_event = self._get_typed_event(
            context,
            workspace_id,
            str(request_event.payload["decision_id"]),
            "DECISION_CREATED",
        )
        evidence_event = self._get_typed_event(
            context,
            workspace_id,
            str(request_event.payload["evidence_id"]),
            "EVIDENCE_ADMITTED",
        )
        ask_event = self._get_typed_event(
            context,
            workspace_id,
            str(decision_event.payload["ask_id"]),
            "ASK_ANSWERED",
        )
        export_id = str(uuid5(NAMESPACE_URL, f"{workspace_id}:{approval_id}:evidence-export"))
        package = {
            "schema": "nexora.customer-evidence-export.v1",
            "export_id": export_id,
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
            "workspace_id": workspace_id,
            "exported_by": context.user_id,
            "evidence": {
                "record_id": evidence_event.event_id,
                "filename": evidence_event.payload["filename"],
                "sha256": evidence_event.payload["source_sha256"],
                "validation_status": evidence_event.payload["validation_status"],
            },
            "ask": {
                "record_id": ask_event.event_id,
                "question": ask_event.payload["question"],
                "answer": ask_event.payload["answer"],
                "evidence_references": ask_event.payload["evidence_references"],
            },
            "decision": {
                "record_id": decision_event.event_id,
                "decision_id": decision_event.payload["decision_id"],
                "decision": decision_event.payload["decision"],
                "rationale": decision_event.payload["rationale"],
                "created_by": decision_event.payload["created_by"],
            },
            "approval": {
                "request_id": approval_id,
                "state": approval["state"],
                "requested_at": request_event.occurred_at,
                "requesting_actor": approval["requesting_actor"],
                "decision_actor": approval.get("decision_actor"),
                "history": [
                    dict(event.payload["history"])
                    for event in transitions
                ],
                "source_references": request_event.payload["source_references"],
            },
        }
        return self.repository.append(
            context=context,
            workspace_id=workspace_id,
            event_type="EVIDENCE_EXPORT_CREATED",
            idempotency_key=f"export:{workspace_id}:{approval_id}",
            payload={"export_id": export_id, "package": package},
        )

    def resume_workspace(
        self, context: AuthenticatedTenantContext, workspace_id: str
    ) -> dict[str, Any]:
        events = self._require_workspace(context, workspace_id)
        workspace = next(event for event in events if event.event_type == "WORKSPACE_CREATED")
        return {
            "workspace": _event_dict(workspace),
            "evidence": [
                _event_dict(event)
                for event in events
                if event.event_type == "EVIDENCE_ADMITTED"
            ],
            "asks": [
                _event_dict(event) for event in events if event.event_type == "ASK_ANSWERED"
            ],
            "decisions": [
                _event_dict(event)
                for event in events
                if event.event_type == "DECISION_CREATED"
            ],
            "approvals": [
                _event_dict(event)
                for event in events
                if event.event_type in {"APPROVAL_REQUESTED", "APPROVAL_TRANSITIONED"}
            ],
            "exports": [
                _event_dict(event)
                for event in events
                if event.event_type == "EVIDENCE_EXPORT_CREATED"
            ],
        }

    def load_evidence(
        self,
        context: AuthenticatedTenantContext,
        workspace_id: str,
        evidence_id: str,
    ) -> bytes:
        self._require_workspace(context, workspace_id)
        return self._load_source(
            context, self._find_evidence(context, workspace_id, evidence_id)
        )

    def _load_source(
        self, context: AuthenticatedTenantContext, evidence: CustomerWorkflowEvent
    ) -> bytes:
        if self.repository.stores_evidence_in_database:
            encrypted_source = self.repository.get_evidence_ciphertext(context, evidence)
            try:
                content = self._evidence_cipher.decrypt(encrypted_source)
            except InvalidToken as exc:
                raise CustomerWorkflowError(
                    "encrypted customer evidence failed integrity checks"
                ) from exc
            scan = scan_upload(str(evidence.payload["filename"]), content)
            if scan["sha256"] != evidence.payload["source_sha256"]:
                raise CustomerWorkflowError("customer evidence failed its stored digest check")
            return content
        relative = Path(str(evidence.payload["encrypted_source"]))
        source = (self.evidence_root / relative).resolve()
        if not source.is_relative_to(self.evidence_root):
            raise CustomerWorkflowError("customer evidence locator is outside the configured root")
        try:
            content = self._evidence_cipher.decrypt(source.read_bytes())
        except (InvalidToken, OSError) as exc:
            raise CustomerWorkflowError("encrypted customer evidence is unavailable") from exc
        scan = scan_upload(str(evidence.payload["filename"]), content)
        if scan["sha256"] != evidence.payload["source_sha256"]:
            raise CustomerWorkflowError("customer evidence failed its stored digest check")
        return content

    def _find_evidence(self, context, workspace_id, evidence_id):
        event = self.repository.get(context, workspace_id, evidence_id)
        if event.event_type != "EVIDENCE_ADMITTED":
            raise CustomerWorkflowError("record is not an admitted evidence item")
        return event

    def _get_typed_event(
        self, context, workspace_id, event_id, event_type, *, key_field=None
    ):
        events = self._require_workspace(context, workspace_id)
        for event in events:
            if event.event_type != event_type:
                continue
            if (
                event.payload.get(key_field or "event_id") == event_id
                or event.event_id == event_id
            ):
                return event
        raise PermissionError(f"{event_type.lower()} is not available in this tenant workspace")

    def _require_workspace(self, context, workspace_id):
        self._context(context)
        events = self.repository.list_workspace_events(context, workspace_id)
        if not any(event.event_type == "WORKSPACE_CREATED" for event in events):
            raise PermissionError("customer workspace is not available in this tenant")
        return events

    @staticmethod
    def _context(context):
        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("verified authenticated tenant context is required")
        if context.organization_id != context.tenant_id:
            raise PermissionError("customer workflow tenant scope is invalid")
        return context


def _analysis_to_dict(analysis: ProspectAnalysis) -> dict[str, Any]:
    result = asdict(analysis)
    result.pop("analysis_timestamp", None)
    result.pop("expires_at", None)
    return result


def _approval_to_dict(request: ApprovalRequest) -> dict[str, Any]:
    result = asdict(request)
    result.pop("created_at", None)
    result["decision_at"] = request.decision_at.isoformat() if request.decision_at else None
    return result


def _approval_from_dict(payload: Mapping[str, Any]) -> ApprovalRequest:
    return ApprovalRequest(
        request_id=str(payload["request_id"]),
        organization_id=str(payload["organization_id"]),
        tenant_id=str(payload["tenant_id"]),
        subject_id=str(payload["subject_id"]),
        requested_action=str(payload["requested_action"]),
        state=str(payload["state"]),
        requesting_actor=str(payload["requesting_actor"]),
        reason=str(payload["reason"]),
        created_at=_timestamp(payload["created_at"]),
        decision_actor=payload.get("decision_actor"),
        decision_at=_timestamp(payload["decision_at"]) if payload.get("decision_at") else None,
        workflow_stage=str(payload["workflow_stage"]),
        current_approver_role=str(payload["current_approver_role"]),
        compatibility_id=payload.get("compatibility_id"),
        escalated_to=payload.get("escalated_to"),
    )


def _event_dict(event: CustomerWorkflowEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "workspace_id": event.workspace_id,
        "actor_id": event.actor_id,
        "occurred_at": event.occurred_at,
        "payload": dict(event.payload),
    }


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
