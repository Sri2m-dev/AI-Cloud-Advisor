from datetime import date, datetime, timezone

import pytest

from data_fabric.foundation import TenantContext
from data_fabric.foundation.exceptions import DataFabricTenantBoundaryError
from repositories.aws_cur_ingestion_repository import SupabaseAwsCurIngestionRepository
from services.aws_cur_ingestion_engine import AwsCurIngestionEngine


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.selected_fields = None
        self.filters = []

    def select(self, fields):
        self.selected_fields = fields
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def execute(self):
        return FakeResponse(self.data)


class FakeSupabaseClient:
    def __init__(self, data):
        self.query = FakeQuery(data)
        self.table_name = None

    def table(self, name):
        self.table_name = name
        return self.query


def mapping_row(**overrides):
    row = {
        "organization_id": "org-a",
        "tenant_id": "tenant-a",
        "payer_account_id": "payer-a",
        "account_id": "member-a",
        "status": "active",
        "effective_from": date(2026, 1, 1),
        "effective_to": None,
    }
    row.update(overrides)
    return row


def test_mapping_projection_is_tenant_scoped_and_returns_effective_dates():
    effective_from = date(2026, 1, 1)
    effective_to = date(2026, 12, 31)
    client = FakeSupabaseClient(
        [mapping_row(effective_from=effective_from, effective_to=effective_to)]
    )
    context = TenantContext("org-a", "tenant-a")

    mapping = next(iter(SupabaseAwsCurIngestionRepository(client).list_account_mappings(context)))

    assert client.table_name == "cloud_account_mapping"
    assert client.query.selected_fields == (
        "organization_id,tenant_id,payer_account_id,account_id,status,"
        "effective_from,effective_to"
    )
    assert client.query.filters == [
        ("organization_id", context.organization_id),
        ("tenant_id", context.tenant_id),
    ]
    assert mapping.effective_from is effective_from
    assert mapping.effective_to is effective_to
    assert isinstance(mapping.effective_from, date)
    assert isinstance(mapping.effective_to, date)


def test_nullable_effective_to_passes_through_unchanged():
    client = FakeSupabaseClient([mapping_row(effective_to=None)])
    context = TenantContext("org-a", "tenant-a")

    mapping = next(iter(SupabaseAwsCurIngestionRepository(client).list_account_mappings(context)))

    assert mapping.effective_to is None


def test_missing_effective_from_fails_closed_in_engine():
    mapping = next(
        iter(
            SupabaseAwsCurIngestionRepository(
                FakeSupabaseClient([mapping_row(effective_from=None)])
            ).list_account_mappings(TenantContext("org-a", "tenant-a"))
        )
    )

    assert not AwsCurIngestionEngine._has_active_account_mapping(
        (mapping,),
        "payer-a",
        "member-a",
        datetime(2026, 7, 2, tzinfo=timezone.utc),
        datetime(2026, 7, 2, 1, tzinfo=timezone.utc),
    )


def test_foreign_mapping_is_rejected_by_engine_tenant_guard():
    context = TenantContext("org-a", "tenant-a")
    mapping = next(
        iter(
            SupabaseAwsCurIngestionRepository(
                FakeSupabaseClient([mapping_row(organization_id="org-b", tenant_id="tenant-b")])
            ).list_account_mappings(context)
        )
    )

    with pytest.raises(DataFabricTenantBoundaryError):
        AwsCurIngestionEngine._validate_mapping_scope(context, (mapping,))
