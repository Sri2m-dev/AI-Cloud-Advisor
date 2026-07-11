from __future__ import annotations
from datetime import datetime, timezone
import pytest
from data_fabric.adapters.supabase import DataFabricDatabaseConfig, SupabaseDataFabricClient
from data_fabric.foundation import TenantContext
from data_fabric.persistence.models import AppendOnlyRecord, MutableRecord
from tests.data_fabric.supabase_fake import FakeRawSupabaseClient, tenant_filters_seen

def client(raw):
    return SupabaseDataFabricClient(DataFabricDatabaseConfig("https://example.supabase.co","server-side-secret",max_retries=0), raw_client=raw)

def tc(): return TenantContext("org-1","tenant-1")
NOW=datetime(2026,1,1,tzinfo=timezone.utc)
import pytest
from data_fabric.adapters.supabase import SupabaseIdempotencyRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError
from data_fabric.orchestration import IdempotencyState

def repo():
    raw=FakeRawSupabaseClient(); return SupabaseIdempotencyRepository(client(raw)), raw

def test_reserve_replay_complete_fail_expire_and_tenant_isolation():
    r,raw=repo(); first=r.reserve(tc(),"key-1","hash-1")
    assert first.payload["status"] == "in_progress"
    assert r.reserve(tc(),"key-1","hash-1").revision == 1
    assert r.compare_payload_hash(tc(),"key-1","hash-1") is True
    with pytest.raises(SupabaseAdapterConflictError): r.reserve(tc(),"key-1","hash-2")
    completed=r.mark_completed(tc(),"key-1","result-1")
    assert completed.payload["status"] == "completed"
    assert r.get_status(tc(),"key-1") is IdempotencyState.COMPLETED
    assert r.get(TenantContext("org-1","tenant-2"),"key-1") is None
    failed=r.reserve(tc(),"key-2","hash-x"); r.mark_failed(tc(),"key-2","bad")
    assert r.get_status(tc(),"key-2") is IdempotencyState.FAILED
    r.reserve(tc(),"key-2","hash-x")
    r.mark_expired(tc(),"key-2")
    assert r.get_status(tc(),"key-2") is IdempotencyState.EXPIRED
    assert tenant_filters_seen(raw,"data_fabric.idempotency_records")

def test_direct_update_and_deactivate_are_rejected():
    r,_=repo(); record=r.reserve(tc(),"key-1","hash-1")
    with pytest.raises(SupabaseAdapterConflictError): r.update(record,expected_revision=1)
    with pytest.raises(SupabaseAdapterConflictError): r.deactivate(tc(),"key-1")
