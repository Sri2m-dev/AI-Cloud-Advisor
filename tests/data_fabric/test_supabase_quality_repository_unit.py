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
from data_fabric.adapters.supabase import SupabaseQualityAssessmentRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError

def repo():
    raw=FakeRawSupabaseClient(); return SupabaseQualityAssessmentRepository(client(raw)), raw

def assessment(aid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1", score=72):
    return AppendOnlyRecord(record_id=aid,organization_id="org-1",tenant_id="tenant-1",created_at=NOW,updated_at=NOW,payload={"subject_type":"entity","subject_id":"22222222-2222-4222-8222-222222222222","overall_score":score,"trust_score":score,"decision":"allow","dimensions":{"freshness":score},"assessed_at":NOW})

def test_quality_append_latest_score_filter_and_tenant_isolation():
    r,raw=repo(); first=r.append(assessment()); second=r.append(assessment("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",55))
    assert r.get(tc(), first.record_id) is not None
    assert r.get_latest_by_subject(tc(),"entity","22222222-2222-4222-8222-222222222222").record_id in {first.record_id, second.record_id}
    assert r.find_by_decision(tc(),"allow")
    assert len(r.find_below_score(tc(),60)) == 1
    assert r.get(TenantContext("org-1","tenant-2"), first.record_id) is None
    assert tenant_filters_seen(raw,"data_fabric.quality_assessments")

def test_quality_duplicate_and_update_rejected():
    r,_=repo(); rec=assessment(); r.append(rec)
    with pytest.raises(SupabaseAdapterOperationError): r.append(rec)
    with pytest.raises(SupabaseAdapterOperationError): r.update(rec)
