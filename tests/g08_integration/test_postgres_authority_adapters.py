"""Opt-in read-only PostgreSQL checks for a disposable G08 adapter fixture.

Set NEXORA_G08_TEST_DSN, NEXORA_G08_TEST_ALLOW=YES, and the fixture identifiers
only for a local database named nexora_g08_adapter_test. These tests never create
or modify fixture rows; every transaction is rolled back.
"""

from __future__ import annotations

import os

import psycopg2
import pytest
from psycopg2.extensions import parse_dsn

from auth.authenticated_tenant import ProtectedWorkflowUnavailable
from repositories.g08_postgres_authority import (
    PostgresFenceGenerationStore,
    PostgresG08PolicyAuthority,
    PostgresG08UnitOfWork,
)
from services.g08_owner_authorization import OwnerDenied, OwnerDependencyUnavailable

DATABASE_NAME = "nexora_g08_adapter_test"


def _connection():
    dsn = os.environ.get("NEXORA_G08_TEST_DSN")
    if not dsn or os.environ.get("NEXORA_G08_TEST_ALLOW") != "YES":
        pytest.skip("explicit disposable PostgreSQL test target is not configured")
    try:
        params = parse_dsn(dsn)
    except psycopg2.Error as error:
        pytest.fail(f"invalid disposable PostgreSQL DSN: {error}")
    if (
        params.get("dbname") != DATABASE_NAME
        or params.get("host", "localhost").lower() not in {"localhost", "127.0.0.1", "::1"}
    ):
        pytest.fail("G08 adapter tests refuse any non-local or non-disposable database target")
    connection = psycopg2.connect(dsn)
    if connection.get_dsn_parameters().get("dbname") != DATABASE_NAME:
        connection.close()
        pytest.fail("connected PostgreSQL database identity does not match the test target")
    connection.autocommit = False
    return connection


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"disposable PostgreSQL fixture is missing {name}")
    return value


class _NoCanonicalWrites:
    def acquire_global_lock(self, cursor):
        raise AssertionError("not used by read-only PostgreSQL checks")

    def decision_time(self, cursor):
        raise AssertionError("not used by read-only PostgreSQL checks")

    def load(self, cursor, operation_id):
        raise AssertionError("not used by read-only PostgreSQL checks")

    def stage_admission(self, cursor, authorization, entry, operator):
        raise AssertionError("not used by read-only PostgreSQL checks")

    def stage_status(self, cursor, authorization, entry, operator):
        raise AssertionError("not used by read-only PostgreSQL checks")

    def stage_execution(self, cursor, authorization, request, operator, evidence):
        raise AssertionError("not used by read-only PostgreSQL checks")

    def read_receipt(self, cursor, authorization_id, operation_id, operator):
        raise AssertionError("not used by read-only PostgreSQL checks")


def test_missing_postgres_dependencies_fail_closed():
    with pytest.raises(OwnerDependencyUnavailable, match="live PostgreSQL"):
        PostgresG08PolicyAuthority(None)
    with pytest.raises(ProtectedWorkflowUnavailable, match="idle explicit PostgreSQL"):
        PostgresG08UnitOfWork(None, _NoCanonicalWrites())


def _transaction(connection):
    unit_of_work = PostgresG08UnitOfWork(connection, _NoCanonicalWrites())
    unit_of_work.begin_read_committed()
    unit_of_work.cursor.execute("SELECT clock_timestamp()")
    return unit_of_work, unit_of_work.cursor.fetchone()[0]


def test_postgres_d10_policy_and_approval_evidence_are_persisted():
    connection = _connection()
    try:
        authorization_id = _required("NEXORA_G08_TEST_AUTHORIZATION_ID")
        authority = PostgresG08PolicyAuthority(connection)
        version = authority.current_version(authorization_id)
        policy = authority.policy(authorization_id, version)
        approvals = authority.approvals(authorization_id, version)
        assert policy.claims["authorization_id"] == authorization_id
        assert policy.claims["version"] == version
        assert approvals
        assert all(item.claims["policy_version"] == version for item in approvals)
    finally:
        connection.rollback()
        connection.close()


def test_postgres_d10_revalidates_current_policy_approvals_and_revocations():
    authorization_id = _required("NEXORA_G08_TEST_AUTHORIZATION_ID")
    connection = _connection()
    try:
        authority = PostgresG08PolicyAuthority(connection)
        version = authority.current_version(authorization_id)
        approvals = authority.approvals(authorization_id, version)
        approval_ids = tuple(sorted(item.claims["approval_id"] for item in approvals))
        connection.rollback()
        unit_of_work, decision_time = _transaction(connection)
        authority.assert_current_in_transaction(
            unit_of_work,
            authorization_id,
            version,
            approval_ids,
            decision_time,
        )
    finally:
        connection.rollback()
        connection.close()


def test_postgres_d10_rejects_stale_policy_version():
    authorization_id = _required("NEXORA_G08_TEST_AUTHORIZATION_ID")
    stale_version = _required("NEXORA_G08_TEST_STALE_POLICY_VERSION")
    connection = _connection()
    try:
        authority = PostgresG08PolicyAuthority(connection)
        connection.rollback()
        unit_of_work, decision_time = _transaction(connection)
        with pytest.raises(OwnerDenied, match="policy changed"):
            authority.assert_current_in_transaction(
                unit_of_work,
                authorization_id,
                stale_version,
                (),
                decision_time,
            )
    finally:
        connection.rollback()
        connection.close()


def test_postgres_fencing_generation_is_scope_bound_and_transactional():
    connection = _connection()
    try:
        scope = {
            "authorization_id": _required("NEXORA_G08_TEST_AUTHORIZATION_ID"),
            "operation_id": _required("NEXORA_G08_TEST_OPERATION_ID"),
            "tenant_id": _required("NEXORA_G08_TEST_TENANT_ID"),
            "organization_id": _required("NEXORA_G08_TEST_ORGANIZATION_ID"),
            "action": _required("NEXORA_G08_TEST_ACTION"),
            "target_resource": _required("NEXORA_G08_TEST_TARGET_RESOURCE"),
        }
        expected = int(_required("NEXORA_G08_TEST_FENCE_GENERATION"))
        unit_of_work, _ = _transaction(connection)
        assert PostgresFenceGenerationStore().current_generation_in_transaction(
            unit_of_work, scope
        ) == expected
    finally:
        connection.rollback()
        connection.close()
