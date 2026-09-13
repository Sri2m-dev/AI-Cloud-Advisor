"""Tenant-authorized live-source control and atomic governed evidence publication."""

import json
import os
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

from auth.authenticated_tenant import AuthenticatedTenantContext
from auth.role_constants import CANONICAL_ROLES
from connector_adapters.live_cost import (
    AWSLiveCostConnector,
    AzureLiveCostConnector,
    ProviderFailure,
    failure_category,
    validate_configuration,
)
from connector_adapters.m365_discovery import M365DiscoveryConnector
from connector_orchestration.scheduler import OrchestrationSchedule, ScheduleType
from connector_orchestration.trigger import ConnectorTriggerType
from connector_registry import ConnectorRegistry
from connector_registry.live_sources import LiveSourceRepository
from connector_secrets.scoped import ScopedCredentialProvider
from data_fabric.source_facts import SourceFactService
from data_fabric.source_facts.adapters import ConnectorSourceFactAdapter
from data_fabric.source_facts.models import FactType, RunMode, RunStatus, SourceInstance

ADMIN_ROLES = frozenset({"super_admin", "client_admin"})


def persistence_boundary(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except sqlite3.Error:
            raise ProviderFailure("PERSISTENCE") from None
    return call


class LiveSourceService:
    def __init__(self, repository, *, factories=None, clock=None):
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.registry = ConnectorRegistry()
        for adapter in (AWSLiveCostConnector, AzureLiveCostConnector, M365DiscoveryConnector):
            self.registry.register_connector(adapter)
        self.factories = factories or {
            "aws": AWSLiveCostConnector,
            "azure": AzureLiveCostConnector,
            "m365": M365DiscoveryConnector,
        }

    @staticmethod
    def authorize(context, *, admin=False):
        if not isinstance(context, AuthenticatedTenantContext):
            raise PermissionError("Authenticated tenant context is required")
        if context.role not in (ADMIN_ROLES if admin else CANONICAL_ROLES):
            raise PermissionError("Tenant administrator authority is required")

    def _audit(self, db, context, source_id, action):
        db.execute("INSERT INTO connector_control_audit VALUES (?,?,?,?,?,?,?)", (
            str(uuid4()), context.organization_id, context.tenant_id, source_id,
            context.user_id, action, self.clock().isoformat(),
        ))

    def _instance(self, context, row, enabled):
        connector_type = "saas_api" if row["provider"] == "m365" else "cloud_api"
        connector_name = (
            "m365.discovery" if row["provider"] == "m365" else f"{row['provider']}.live_cost"
        )
        return SourceInstance(
            row["source_id"], context.organization_id, context.tenant_id,
            connector_type, row["provider"], connector_name, "1.1.0",
            f"connector-config:{row['source_id']}", f"connector-secret:{row['source_id']}",
            enabled=enabled, updated_at=self.clock(),
        )

    @staticmethod
    def _public(row):
        return {k: v for k, v in row.items() if k not in {"credential_ciphertext", "config_json"}}

    @persistence_boundary
    def list_sources(self, context):
        self.authorize(context)
        with self.repository.transaction() as db:
            rows = db.execute(
                "SELECT c.*, COALESCE((SELECT e.status FROM connector_executions e "
                "WHERE e.organization_id=c.organization_id AND e.tenant_id=c.tenant_id "
                "AND e.source_id=c.source_id ORDER BY e.queued_at DESC, e.rowid DESC LIMIT 1), "
                "'NEVER_SYNCED') sync_status FROM connector_source_config c "
                "WHERE c.organization_id=? AND c.tenant_id=? ORDER BY c.created_at",
                (context.organization_id, context.tenant_id),
            ).fetchall()
            return tuple(self._public(dict(row)) for row in rows)

    @persistence_boundary
    def executions(self, context, source_id):
        self.authorize(context)
        with self.repository.transaction() as db:
            self.repository.source(db, context, source_id)
            return tuple(dict(row) for row in db.execute(
                "SELECT * FROM connector_executions WHERE organization_id=? AND tenant_id=? "
                "AND source_id=? ORDER BY queued_at DESC LIMIT 100",
                (context.organization_id, context.tenant_id, source_id),
            ))

    @staticmethod
    def _material(provider, material):
        expected = {"external_id"} if provider == "aws" else {"client_secret"}
        if set(material) - expected or not all(isinstance(v, str) for v in material.values()):
            raise ProviderFailure("INVALID_CONFIGURATION")
        if provider in {"azure", "m365"} and not material.get("client_secret"):
            raise ProviderFailure("AUTHENTICATION")
        return material

    @persistence_boundary
    def create(self, context, *, provider, display_name, configuration, secrets):
        self.authorize(context, admin=True)
        config = validate_configuration(provider, configuration)
        if not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 100:
            raise ProviderFailure("INVALID_CONFIGURATION")
        source_id, now = str(uuid4()), self.clock().isoformat()
        ciphertext = ScopedCredentialProvider.seal(
            context, source_id, self._material(provider, secrets),
        )
        row = {"source_id": source_id, "provider": provider}
        with self.repository.transaction() as db:
            SourceFactService(context.fabric_context, self.repository.bound(db)).register(
                self._instance(context, row, False),
            )
            account_identifier = (
                config.get("account_id")
                or config.get("subscription_id")
                or config.get("tenant_id")
            )
            db.execute(
                "INSERT INTO connector_source_config (organization_id,tenant_id,source_id,"
                "provider,account_id,display_name,config_json,credential_ciphertext,status,"
                "created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (context.organization_id, context.tenant_id, source_id, provider,
                 account_identifier, display_name.strip(),
                 json.dumps(config), ciphertext, "DRAFT", context.user_id, now, now),
            )
            self._audit(db, context, source_id, "SOURCE_CREATED")
            return self._public(self.repository.source(db, context, source_id))

    @persistence_boundary
    def configure(self, context, source_id, *, configuration, secrets):
        """Editing invalidates validation and requires explicit reactivation."""
        self.authorize(context, admin=True)
        with self.repository.transaction() as db:
            row = self.repository.source(db, context, source_id)
            self._idle(db, context, source_id)
            if row["status"] == "VALIDATING":
                raise ProviderFailure("BUSY")
            config = validate_configuration(row["provider"], configuration)
            ciphertext = ScopedCredentialProvider.seal(
                context, source_id, self._material(row["provider"], secrets),
            )
            account_identifier = (
                config.get("account_id")
                or config.get("subscription_id")
                or config.get("tenant_id")
            )
            db.execute(
                "UPDATE connector_source_config SET config_json=?,credential_ciphertext=?,"
                "account_id=?,status='DRAFT',schedule_enabled=0,next_run_at=NULL,updated_at=? "
                "WHERE organization_id=? AND tenant_id=? AND source_id=?",
                (
                    json.dumps(config),
                    ciphertext,
                    account_identifier,
                    self.clock().isoformat(),
                    context.organization_id,
                    context.tenant_id,
                    source_id,
                ),
            )
            SourceFactService(context.fabric_context, self.repository.bound(db)).register(
                self._instance(context, row, False),
            )
            self._audit(db, context, source_id, "CONFIGURATION_CHANGED")

    def _connector(self, context, row):
        connector_key = (
            "m365.discovery" if row["provider"] == "m365" else f"{row['provider']}.live_cost"
        )
        registered = self.registry.get_connector(connector_key)
        if registered is None or not registered.enabled:
            raise ProviderFailure("DISABLED")
        return self.factories[row["provider"]](
            json.loads(row["config_json"]),
            ScopedCredentialProvider(context, row["source_id"], row["credential_ciphertext"]),
            now=self.clock(),
        )

    @staticmethod
    def _read(connector):
        if not connector.authenticate():
            raise ProviderFailure("AUTHENTICATION")
        raw = connector.extract()
        records = connector.normalize(raw)
        valid, _ = connector.validate(records)
        if not valid or len(raw) != len(records):
            raise ProviderFailure("MALFORMED_RESPONSE")
        return records

    @staticmethod
    def _close(connector):
        if connector is not None:
            try:
                connector.close()
            except Exception:
                pass  # Do not replace the safe result with credential-bearing text.

    @staticmethod
    def _idle(db, context, source_id):
        active = db.execute(
            "SELECT 1 FROM connector_executions WHERE organization_id=? AND tenant_id=? "
            "AND source_id=? AND status IN ('QUEUED','RUNNING')",
            (context.organization_id, context.tenant_id, source_id),
        ).fetchone()
        if active:
            raise ProviderFailure("BUSY")

    @persistence_boundary
    def validate_connection(self, context, source_id):
        self.authorize(context, admin=True)
        with self.repository.transaction() as db:
            row = self.repository.source(db, context, source_id)
            self._idle(db, context, source_id)
            if row["status"] in {"ACTIVE", "VALIDATING"}:
                raise ProviderFailure("BUSY")
            db.execute(
                "UPDATE connector_source_config SET status='VALIDATING',updated_at=? "
                "WHERE organization_id=? AND tenant_id=? AND source_id=?",
                (self.clock().isoformat(), context.organization_id, context.tenant_id, source_id),
            )
        connector, category = None, None
        try:
            connector = self._connector(context, row)
            self._read(connector)  # Identity and read-only permissions check.
        except Exception as error:
            category = failure_category(error)
        finally:
            self._close(connector)
        with self.repository.transaction() as db:
            current = self.repository.source(db, context, source_id)
            if current["status"] != "VALIDATING":
                raise ProviderFailure("DISABLED")
            summary = str(ProviderFailure(category)) if category else None
            db.execute(
                "UPDATE connector_source_config SET status=?,last_error_category=?,"
                "safe_error_summary=?,updated_at=? WHERE organization_id=? AND tenant_id=? "
                "AND source_id=?",
                ("ERROR" if category else "READY", category, summary, self.clock().isoformat(),
                 context.organization_id, context.tenant_id, source_id),
            )
            self._audit(db, context, source_id, "VALIDATION_FAILED" if category else "VALIDATED")
        return {"status": "ERROR" if category else "READY", "error_category": category,
                "safe_error_summary": summary}

    @persistence_boundary
    def set_active(self, context, source_id, active):
        self.authorize(context, admin=True)
        with self.repository.transaction() as db:
            row = self.repository.source(db, context, source_id)
            if active and row["status"] != "READY":
                raise ProviderFailure("VALIDATION_REQUIRED")
            db.execute(
                "UPDATE connector_source_config SET status=?,updated_at=?,schedule_enabled=0,"
                "next_run_at=NULL WHERE organization_id=? AND tenant_id=? AND source_id=?",
                ("ACTIVE" if active else "DISABLED", self.clock().isoformat(),
                 context.organization_id, context.tenant_id, source_id),
            )
            SourceFactService(context.fabric_context, self.repository.bound(db)).register(
                self._instance(context, row, active),
            )
            self._audit(db, context, source_id, "ACTIVATED" if active else "DISABLED")

    @persistence_boundary
    def set_schedule(self, context, source_id, *, enabled, cadence_seconds=86400):
        self.authorize(context, admin=True)
        if type(cadence_seconds) is not int or not 3600 <= cadence_seconds <= 2592000:
            raise ProviderFailure("INVALID_CONFIGURATION")
        with self.repository.transaction() as db:
            row = self.repository.source(db, context, source_id)
            if enabled and row["status"] != "ACTIVE":
                raise ProviderFailure("DISABLED")
            schedule = OrchestrationSchedule(source_id, ScheduleType.INTERVAL, bool(enabled),
                                             cadence_seconds)
            next_run = (self.clock() + timedelta(seconds=schedule.interval_seconds)).isoformat()
            db.execute(
                """
                UPDATE connector_source_config SET schedule_enabled=?,cadence_seconds=?,
                next_run_at=?,updated_at=? WHERE organization_id=? AND tenant_id=? AND source_id=?
                """,
                (
                    int(enabled),
                    cadence_seconds,
                    next_run if enabled else None,
                    self.clock().isoformat(),
                    context.organization_id,
                    context.tenant_id,
                    source_id,
                ),
            )
            self._audit(db, context, source_id, "SCHEDULE_CHANGED")

    @persistence_boundary
    def sync(self, context, source_id, *, request_key, trigger=ConnectorTriggerType.MANUAL):
        self.authorize(context, admin=True)
        if trigger not in {ConnectorTriggerType.MANUAL, ConnectorTriggerType.SCHEDULED}:
            raise ProviderFailure("INVALID_TRIGGER")
        if not isinstance(request_key, str) or not 1 <= len(request_key) <= 150:
            raise ProviderFailure("INVALID_REQUEST")
        scope = (context.organization_id, context.tenant_id, source_id)
        with self.repository.transaction() as db:
            row = self.repository.source(db, context, source_id)
            if not self.repository.bound(db).instance_enabled(*scope):
                raise ProviderFailure("DISABLED")
            previous = db.execute(
                "SELECT * FROM connector_executions WHERE organization_id=? AND tenant_id=? "
                "AND source_id=? AND request_key=?", (*scope, request_key),
            ).fetchone()
            if previous:
                return dict(previous)
            if trigger == ConnectorTriggerType.SCHEDULED and (
                not row["schedule_enabled"] or not row["next_run_at"]
                or row["next_run_at"] > self.clock().isoformat()
            ):
                raise ProviderFailure("NOT_DUE")
            self._idle(db, context, source_id)
            execution_id, now = str(uuid4()), self.clock().isoformat()
            db.execute(
                """
                INSERT INTO connector_executions (
                    execution_id,organization_id,tenant_id,source_id,
                    request_key,trigger_type,requested_by,status,queued_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (execution_id, *scope, request_key, trigger.value, context.user_id, "QUEUED", now),
            )
            self._audit(db, context, source_id, "SYNC_QUEUED")
        connector, count = None, 0
        try:
            with self.repository.transaction() as db:
                db.execute("UPDATE connector_executions SET status='RUNNING',started_at=? "
                           "WHERE execution_id=?", (self.clock().isoformat(), execution_id))
            connector = self._connector(context, row)
            records = self._read(connector)
            count = len(records)
            type_mapping = {
                "cloud_cost": FactType.CLOUD_COST,
                "license_sku": FactType.CONTRACT_TERM,
                "identity_user": FactType.RESOURCE_IDENTITY,
                "license_assignment": FactType.LICENSE_ASSIGNMENT,
                "application": FactType.RESOURCE_IDENTITY,
            }
            adapted = ConnectorSourceFactAdapter().adapt(records, type_mapping)
            facts = tuple(
                replace(
                    fact,
                    provenance={
                        **fact.provenance,
                        "provider": row["provider"],
                        "source_id": source_id,
                        "execution_id": execution_id,
                        "account_id": row["account_id"],
                    },
                    lineage={"execution_id": execution_id},
                )
                for fact in adapted
            )
            with self.repository.transaction() as db:
                current = self.repository.source(db, context, source_id)
                running = db.execute(
                    "SELECT status FROM connector_executions WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()
                if (
                    not running
                    or running[0] != "RUNNING"
                    or not self.repository.bound(db).instance_enabled(*scope)
                ):
                    raise ProviderFailure("DISABLED")
                schema_name = "discovery" if row["provider"] == "m365" else "cloud_cost"
                publication = SourceFactService(
                    context.fabric_context, self.repository.bound(db)
                ).publish(
                    self._instance(context, current, True),
                    facts,
                    run_id=execution_id,
                    mode=RunMode.INCREMENTAL,
                    schema={schema_name: "object"},
                    required_fields=(),
                    correlation_id=execution_id,
                )
                if publication.status is not RunStatus.SUCCESS or publication.quarantined:
                    raise ProviderFailure("EVIDENCE_REJECTED")
                now = self.clock().isoformat()
                db.execute(
                    """
                    UPDATE connector_executions SET status='SUCCEEDED',completed_at=?,
                    records_discovered=?,records_ingested=?,evidence_reference=?
                    WHERE execution_id=?
                    """,
                    (
                        now,
                        count,
                        len(facts),
                        f"sourcefacts:{source_id}:{execution_id}",
                        execution_id,
                    ),
                )
                db.execute(
                    """
                    UPDATE connector_source_config SET status='ACTIVE',last_success_at=?,
                    last_error_category=NULL,safe_error_summary=NULL,updated_at=?,next_run_at=?
                    WHERE organization_id=? AND tenant_id=? AND source_id=?
                    """,
                    (now, now, self._next(current), *scope),
                )
                self._audit(db, context, source_id, "SYNC_SUCCEEDED")
        except Exception as error:
            category = (
                "PERSISTENCE" if isinstance(error, sqlite3.Error) else failure_category(error)
            )
            with self.repository.transaction() as db:
                current = self.repository.source(db, context, source_id)
                db.execute(
                    """
                    UPDATE connector_executions SET status='FAILED',completed_at=?,error_category=?,
                    safe_error_summary=?,records_discovered=?,records_rejected=?
                    WHERE execution_id=? AND status IN ('QUEUED','RUNNING')
                    """,
                    (
                        self.clock().isoformat(),
                        category,
                        str(ProviderFailure(category)),
                        count,
                        count,
                        execution_id,
                    ),
                )
                db.execute(
                    """
                    UPDATE connector_source_config SET status=CASE WHEN status='DISABLED'
                    THEN status ELSE 'ERROR' END,last_error_category=?,safe_error_summary=?,
                    updated_at=?,next_run_at=?
                    WHERE organization_id=? AND tenant_id=? AND source_id=?
                    """,
                    (
                        category,
                        str(ProviderFailure(category)),
                        self.clock().isoformat(),
                        self._next(current),
                        *scope,
                    ),
                )
                self._audit(db, context, source_id, "SYNC_FAILED")
        finally:
            self._close(connector)
        with self.repository.transaction() as db:
            return dict(db.execute("SELECT * FROM connector_executions WHERE execution_id=?",
                                   (execution_id,)).fetchone())

    def _next(self, row):
        return ((self.clock() + timedelta(seconds=row["cadence_seconds"])).isoformat()
                if row["schedule_enabled"] else None)

    def run_due(self, context):
        """A trusted scheduler supplies the same authenticated tenant authority as manual sync."""
        self.authorize(context, admin=True)
        results = []
        for source in self.list_sources(context):
            if (source["schedule_enabled"] and source["next_run_at"]
                    and source["next_run_at"] <= self.clock().isoformat()):
                results.append(self.sync(context, source["source_id"],
                                         request_key=f"scheduled:{source['next_run_at']}",
                                         trigger=ConnectorTriggerType.SCHEDULED))
        return tuple(results)


def live_source_service(database=None):
    path = database or os.getenv("NEXORA_UNIVERSAL_EVIDENCE_DB")
    if not path:
        if os.getenv("ENVIRONMENT", "").strip().lower() in {"prod", "production"}:
            raise ProviderFailure("PERSISTENCE_CONFIGURATION_REQUIRED")
        path = "cloud_advisor.db"
    return LiveSourceService(LiveSourceRepository(path))
