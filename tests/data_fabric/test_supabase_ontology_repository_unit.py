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
from data_fabric.adapters.supabase import SupabaseOntologyRepository
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError, SupabaseAdapterOperationError

def repo():
    raw=FakeRawSupabaseClient(); return SupabaseOntologyRepository(client(raw)), raw

def concept(cid="compute"):
    return MutableRecord(record_id=cid,organization_id="org-1",tenant_id="tenant-1",created_at=NOW,updated_at=NOW,payload={"canonical_name":cid,"display_name":cid.title(),"concept_type":"compute","synonyms":[cid+" synonym"],"aliases":[],"attributes":{},"version":1})

def rel(rid="11111111-1111-4111-8111-111111111111"):
    return MutableRecord(record_id=rid,organization_id="org-1",tenant_id="tenant-1",created_at=NOW,updated_at=NOW,payload={"source_concept_id":"compute","target_concept_id":"storage","relationship_type":"related_to","attributes":{}})

def test_concept_crud_concurrency_deactivate_and_tenant_isolation():
    r,raw=repo(); rec=r.add_concept(concept())
    assert r.get_concept(tc(),"compute") is not None
    assert r.find_by_canonical_name(tc(),"compute") is not None
    assert r.find_by_synonym(tc(),"compute synonym")
    changed=replace(rec,payload={**dict(rec.payload),"display_name":"Compute Updated"})
    updated=r.update_concept(changed,expected_revision=1)
    assert updated.revision == 2
    with pytest.raises(SupabaseAdapterConflictError): r.update_concept(changed,expected_revision=1)
    deactivated=r.deactivate_concept(tc(),"compute")
    assert r.get_concept(tc(),"compute") is None
    assert r.get_concept(tc(),"compute",include_inactive=True) is not None
    assert tenant_filters_seen(raw,"data_fabric.ontology_concepts")

def test_relationship_crud_and_endpoint_queries():
    r,raw=repo(); r.add_concept(concept("compute")); r.add_concept(concept("storage")); created=r.add_relationship(rel())
    assert r.get_relationship(tc(),created.record_id) is not None
    assert r.list_children(tc(),"compute")
    assert r.list_parents(tc(),"storage")
    updated=r.update_relationship(created,expected_revision=1)
    assert updated.revision == 2
    with pytest.raises(SupabaseAdapterConflictError): r.update_relationship(created,expected_revision=1)
    r.deactivate_relationship(tc(),created.record_id)
    assert tenant_filters_seen(raw,"data_fabric.ontology_relationships")

def test_same_concept_name_allowed_in_another_tenant_and_input_immutable():
    r,_=repo(); c=concept(); original=dict(c.payload); r.add_concept(c)
    other=MutableRecord(record_id="compute",organization_id="org-1",tenant_id="tenant-2",created_at=NOW,updated_at=NOW,payload=original)
    assert r.add_concept(other).tenant_id == "tenant-2"
    assert dict(c.payload) == original
