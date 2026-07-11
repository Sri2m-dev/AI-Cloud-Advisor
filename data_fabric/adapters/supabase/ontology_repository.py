"""Supabase PostgreSQL ontology concept and relationship repository adapter."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError
from data_fabric.adapters.supabase.repository_utils import apply_query_filters, default_page, dt, ensure_inserted, iso, optional_row, page_result, plain_mapping, response_rows
from data_fabric.foundation import TenantContext
from data_fabric.persistence.interfaces import OntologyRepository
from data_fabric.persistence.models import MutableRecord, PageRequest, PageResult, RepositoryQuery

class SupabaseOntologyRepository(OntologyRepository):
    concept_table="ontology_concepts"; relationship_table="ontology_relationships"
    def __init__(self, client:SupabaseDataFabricClient)->None: self.client=client
    def add(self, record:MutableRecord)->MutableRecord: return self.add_concept(record)
    def get(self, tenant_context:TenantContext, record_id:str, *, include_inactive:bool=False)->MutableRecord|None: return self.get_concept(tenant_context,record_id,include_inactive=include_inactive)
    def update(self, record:MutableRecord, *, expected_revision:int)->MutableRecord: return self.update_concept(record,expected_revision=expected_revision)
    def deactivate(self, tenant_context:TenantContext, record_id:str, *, deactivated_by:str|None=None)->MutableRecord: return self.deactivate_concept(tenant_context,record_id,deactivated_by=deactivated_by)
    def add_concept(self, record:MutableRecord)->MutableRecord:
        response=self.client.execute(lambda:self.client.table(self.concept_table).insert(self._concept_to_row(record)).execute())
        return self._row_to_concept(ensure_inserted(response,"ontology concept"))
    def get_concept(self, tc:TenantContext, concept_id:str, *, include_inactive:bool=False)->MutableRecord|None:
        q=self._concept_query(tc).eq("concept_id",concept_id)
        if not include_inactive: q=q.eq("active",True)
        row=optional_row(self.client.execute(lambda:q.limit(1).execute())); return self._row_to_concept(row) if row else None
    def find_by_canonical_name(self, tc:TenantContext, canonical_name:str, *, include_inactive:bool=False)->MutableRecord|None:
        q=self._concept_query(tc).eq("normalized_canonical_name",canonical_name.casefold().strip())
        if not include_inactive: q=q.eq("active",True)
        row=optional_row(self.client.execute(lambda:q.limit(1).execute())); return self._row_to_concept(row) if row else None
    def find_by_synonym(self, tc:TenantContext, synonym:str)->tuple[MutableRecord,...]:
        return tuple(r for r in self.list_concepts(tc).items if synonym in tuple(r.payload.get("synonyms",())))
    def update_concept(self, record:MutableRecord, *, expected_revision:int)->MutableRecord:
        rows=response_rows(self.client.execute(lambda:self.client.rpc("data_fabric_update_ontology_concept",{"p_concept_id":record.record_id,"p_organization_id":record.organization_id,"p_tenant_id":record.tenant_id,"p_expected_revision":expected_revision,"p_concept":self._concept_to_row(record)})))
        if not rows: raise SupabaseAdapterConflictError("stale revision or ontology concept not found")
        return self._row_to_concept(rows[0])
    def deactivate_concept(self, tc:TenantContext, concept_id:str, *, deactivated_by:str|None=None)->MutableRecord:
        current=self.get_concept(tc,concept_id,include_inactive=True)
        if current is None: raise SupabaseAdapterConflictError("ontology concept not found")
        return self.update_concept(replace(current,active=False,deactivated_at=datetime.now(timezone.utc),deactivated_by=deactivated_by),expected_revision=current.revision)
    def list_concepts(self, tc:TenantContext, *, include_inactive:bool=False, page:PageRequest|None=None)->PageResult:
        return self.search(RepositoryQuery(tc,include_inactive=include_inactive,page=default_page(page)))
    def add_relationship(self, record:MutableRecord)->MutableRecord:
        response=self.client.execute(lambda:self.client.table(self.relationship_table).insert(self._relationship_to_row(record)).execute())
        return self._row_to_relationship(ensure_inserted(response,"ontology relationship"))
    def get_relationship(self, tc:TenantContext, relationship_id:str, *, include_inactive:bool=False)->MutableRecord|None:
        q=self._relationship_query(tc).eq("relationship_id",relationship_id)
        if not include_inactive: q=q.eq("active",True)
        row=optional_row(self.client.execute(lambda:q.limit(1).execute())); return self._row_to_relationship(row) if row else None
    def list_relationships(self, tc:TenantContext, *, include_inactive:bool=False)->PageResult:
        q=RepositoryQuery(tc,include_inactive=include_inactive); return self._relationship_search(q)
    def update_relationship(self, record:MutableRecord, *, expected_revision:int)->MutableRecord:
        rows=response_rows(self.client.execute(lambda:self.client.rpc("data_fabric_update_ontology_relationship",{"p_relationship_id":record.record_id,"p_organization_id":record.organization_id,"p_tenant_id":record.tenant_id,"p_expected_revision":expected_revision,"p_relationship":self._relationship_to_row(record)})))
        if not rows: raise SupabaseAdapterConflictError("stale revision or ontology relationship not found")
        return self._row_to_relationship(rows[0])
    def deactivate_relationship(self, tc:TenantContext, relationship_id:str)->MutableRecord:
        current=self.get_relationship(tc,relationship_id,include_inactive=True)
        if current is None: raise SupabaseAdapterConflictError("ontology relationship not found")
        return self.update_relationship(replace(current,active=False,deactivated_at=datetime.now(timezone.utc)),expected_revision=current.revision)
    def list_children(self, tc:TenantContext, concept_id:str)->tuple[MutableRecord,...]: return tuple(self._relationship_search(RepositoryQuery(tc,filters={"source_concept_id":concept_id})).items)
    def list_parents(self, tc:TenantContext, concept_id:str)->tuple[MutableRecord,...]: return tuple(self._relationship_search(RepositoryQuery(tc,filters={"target_concept_id":concept_id})).items)
    def exists(self, tc:TenantContext, record_id:str)->bool: return self.get_concept(tc,record_id,include_inactive=True) is not None
    def count(self, query:RepositoryQuery)->int: return self.search(query).total_count
    def search(self, query:RepositoryQuery)->PageResult:
        q=self._concept_query(query.tenant_context)
        if not query.include_inactive: q=q.eq("active",True)
        response=self.client.execute(lambda:apply_query_filters(q,query).execute())
        return page_result([self._row_to_concept(r) for r in response_rows(response)],query)
    def _relationship_search(self, query:RepositoryQuery)->PageResult:
        q=self._relationship_query(query.tenant_context)
        if not query.include_inactive: q=q.eq("active",True)
        response=self.client.execute(lambda:apply_query_filters(q,query).execute())
        return page_result([self._row_to_relationship(r) for r in response_rows(response)],query)
    def _concept_query(self,tc): return self.client.table(self.concept_table).select("*").eq("organization_id",tc.organization_id).eq("tenant_id",tc.tenant_id)
    def _relationship_query(self,tc): return self.client.table(self.relationship_table).select("*").eq("organization_id",tc.organization_id).eq("tenant_id",tc.tenant_id)
    def _concept_to_row(self,record):
        p=plain_mapping(record.payload); return {"concept_id":record.record_id,"organization_id":record.organization_id,"tenant_id":record.tenant_id,"canonical_name":p.get("canonical_name"),"normalized_canonical_name":str(p.get("canonical_name","")).casefold().strip(),"display_name":p.get("display_name"),"description":p.get("description"),"concept_type":p.get("concept_type"),"parent_concept_id":p.get("parent_concept_id"),"synonyms":p.get("synonyms",[]),"aliases":p.get("aliases",[]),"attributes":plain_mapping(p.get("attributes",{})),"version":int(p.get("version",1)),"active":record.active,"revision":record.revision,"created_at":iso(record.created_at),"updated_at":iso(record.updated_at),"deactivated_at":iso(record.deactivated_at),"deactivated_by":record.deactivated_by,"schema_version":record.schema_version}
    def _row_to_concept(self,row):
        p={"concept_id":row["concept_id"],"canonical_name":row["canonical_name"],"display_name":row["display_name"],"description":row.get("description"),"concept_type":row["concept_type"],"parent_concept_id":row.get("parent_concept_id"),"synonyms":row.get("synonyms") or [],"aliases":row.get("aliases") or [],"attributes":plain_mapping(row.get("attributes",{})),"version":row.get("version",1)}
        return MutableRecord(record_id=row["concept_id"],organization_id=row["organization_id"],tenant_id=row["tenant_id"],created_at=dt(row["created_at"]),updated_at=dt(row["updated_at"]),schema_version=row.get("schema_version",1),metadata={"kind":"ontology_concept"},payload=p,revision=row.get("revision",1),active=row.get("active",True),deactivated_at=dt(row.get("deactivated_at")),deactivated_by=row.get("deactivated_by"))
    def _relationship_to_row(self,record):
        p=plain_mapping(record.payload); return {"relationship_id":record.record_id,"source_concept_id":p.get("source_concept_id"),"target_concept_id":p.get("target_concept_id"),"relationship_type":p.get("relationship_type"),"organization_id":record.organization_id,"tenant_id":record.tenant_id,"attributes":plain_mapping(p.get("attributes",{})),"active":record.active,"revision":record.revision,"created_at":iso(record.created_at),"updated_at":iso(record.updated_at),"deactivated_at":iso(record.deactivated_at),"schema_version":record.schema_version}
    def _row_to_relationship(self,row):
        p={"source_concept_id":row["source_concept_id"],"target_concept_id":row["target_concept_id"],"relationship_type":row["relationship_type"],"attributes":plain_mapping(row.get("attributes",{}))}
        return MutableRecord(record_id=row["relationship_id"],organization_id=row["organization_id"],tenant_id=row["tenant_id"],created_at=dt(row["created_at"]),updated_at=dt(row["updated_at"]),schema_version=row.get("schema_version",1),metadata={"kind":"ontology_relationship"},payload=p,revision=row.get("revision",1),active=row.get("active",True),deactivated_at=dt(row.get("deactivated_at")))
