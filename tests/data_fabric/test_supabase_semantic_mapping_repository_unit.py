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
from dataclasses import replace
from data_fabric.adapters.supabase import SupabaseSemanticMappingRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError, SupabaseAdapterOperationError

def repo():
    raw=FakeRawSupabaseClient(); return SupabaseSemanticMappingRepository(client(raw)), raw

def mapping(mid="11111111-1111-4111-8111-111111111111", confidence=91):
    return MutableRecord(record_id=mid,organization_id="org-1",tenant_id="tenant-1",created_at=NOW,updated_at=NOW,payload={"source_system":"cmdb","source_term":"EC2","source_type":"application","source_identifier":"ec2","provider":"aws","entity_type":"technology","concept_id":"compute","confidence_score":confidence,"mapping_strategy":"explicit","attributes":{}})

def test_mapping_lookup_update_deactivate_and_tenant_isolation():
    r,raw=repo(); rec=r.add(mapping())
    assert r.get(tc(),rec.record_id) is not None
    assert r.find_explicit_mapping(tc(),"cmdb","EC2") is not None
    assert r.list_by_concept(tc(),"compute").total_count == 1
    assert r.list_by_source_system(tc(),"cmdb").total_count == 1
    changed=replace(rec,payload={**dict(rec.payload),"confidence_score":80})
    assert r.update(changed,expected_revision=1).revision == 2
    with pytest.raises(SupabaseAdapterConflictError): r.update(changed,expected_revision=1)
    r.deactivate(tc(),rec.record_id)
    assert r.get(tc(),rec.record_id) is None
    assert tenant_filters_seen(raw,"data_fabric.semantic_mappings")

def test_mapping_duplicate_rejected_and_input_not_mutated():
    r,_=repo(); rec=mapping(); original=dict(rec.payload); r.add(rec)
    with pytest.raises(SupabaseAdapterOperationError): r.add(rec)
    assert dict(rec.payload)==original
