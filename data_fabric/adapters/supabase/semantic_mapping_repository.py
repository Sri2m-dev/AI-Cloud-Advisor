"""Supabase PostgreSQL semantic mapping repository adapter."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError
from data_fabric.adapters.supabase.repository_utils import apply_query_filters, dt, ensure_inserted, iso, optional_row, page_result, plain_mapping, response_rows
from data_fabric.foundation import TenantContext
from data_fabric.persistence.interfaces import SemanticMappingRepository
from data_fabric.persistence.models import MutableRecord, PageResult, RepositoryQuery

class SupabaseSemanticMappingRepository(SemanticMappingRepository):
    table_name="semantic_mappings"
    def __init__(self, client:SupabaseDataFabricClient)->None: self.client=client
    def add(self, record:MutableRecord)->MutableRecord:
        response=self.client.execute(lambda:self.client.table(self.table_name).insert(self._record_to_row(record)).execute())
        return self._row_to_record(ensure_inserted(response,"semantic mapping"))
    def get(self, tc:TenantContext, record_id:str, *, include_inactive:bool=False)->MutableRecord|None:
        q=self._tenant_query(tc).eq("mapping_id",record_id)
        if not include_inactive: q=q.eq("active",True)
        row=optional_row(self.client.execute(lambda:q.limit(1).execute())); return self._row_to_record(row) if row else None
    def find_explicit_mapping(self, tc:TenantContext, source_system:str, source_term:str, *, source_type:str|None=None, source_identifier:str|None=None, provider:str|None=None, entity_type:str|None=None)->MutableRecord|None:
        q=self._tenant_query(tc).eq("source_system",source_system).eq("source_term",source_term).eq("mapping_strategy","explicit").eq("active",True)
        for column,value in (("source_type",source_type),("source_identifier",source_identifier),("provider",provider),("entity_type",entity_type)):
            if value is not None: q=q.eq(column,value)
        row=optional_row(self.client.execute(lambda:q.limit(1).execute())); return self._row_to_record(row) if row else None
    def list_by_concept(self, tc:TenantContext, concept_id:str, *, include_inactive:bool=False)->PageResult: return self.search(RepositoryQuery(tc,filters={"concept_id":concept_id},include_inactive=include_inactive))
    def list_by_source_system(self, tc:TenantContext, source_system:str, *, include_inactive:bool=False)->PageResult: return self.search(RepositoryQuery(tc,filters={"source_system":source_system},include_inactive=include_inactive))
    def update(self, record:MutableRecord, *, expected_revision:int)->MutableRecord:
        rows=response_rows(self.client.execute(lambda:self.client.rpc("data_fabric_update_semantic_mapping",{"p_mapping_id":record.record_id,"p_organization_id":record.organization_id,"p_tenant_id":record.tenant_id,"p_expected_revision":expected_revision,"p_mapping":self._record_to_row(record)})))
        if not rows: raise SupabaseAdapterConflictError("stale revision or semantic mapping not found")
        return self._row_to_record(rows[0])
    def deactivate(self, tc:TenantContext, record_id:str, *, deactivated_by:str|None=None)->MutableRecord:
        current=self.get(tc,record_id,include_inactive=True)
        if current is None: raise SupabaseAdapterConflictError("semantic mapping not found")
        return self.update(replace(current,active=False,deactivated_at=datetime.now(timezone.utc)),expected_revision=current.revision)
    def exists(self, tc:TenantContext, record_id:str)->bool: return self.get(tc,record_id,include_inactive=True) is not None
    def count(self, query:RepositoryQuery)->int: return self.search(query).total_count
    def search(self, query:RepositoryQuery)->PageResult:
        q=self._tenant_query(query.tenant_context)
        if not query.include_inactive: q=q.eq("active",True)
        response=self.client.execute(lambda:apply_query_filters(q,query).execute())
        return page_result([self._row_to_record(r) for r in response_rows(response)],query)
    def _tenant_query(self,tc): return self.client.table(self.table_name).select("*").eq("organization_id",tc.organization_id).eq("tenant_id",tc.tenant_id)
    def _record_to_row(self,record:MutableRecord)->dict[str,Any]:
        p=plain_mapping(record.payload); return {"mapping_id":record.record_id,"organization_id":record.organization_id,"tenant_id":record.tenant_id,"source_system":p.get("source_system"),"source_term":p.get("source_term"),"source_type":p.get("source_type"),"source_identifier":p.get("source_identifier"),"provider":p.get("provider"),"entity_type":p.get("entity_type"),"concept_id":p.get("concept_id"),"confidence_score":p.get("confidence_score",p.get("confidence",100.0)),"mapping_strategy":p.get("mapping_strategy","explicit"),"explanation":p.get("explanation",{}),"attributes":plain_mapping(p.get("attributes",{})),"active":record.active,"revision":record.revision,"created_at":iso(record.created_at),"updated_at":iso(record.updated_at),"deactivated_at":iso(record.deactivated_at),"schema_version":record.schema_version}
    def _row_to_record(self,row:dict[str,Any])->MutableRecord:
        p={"source_system":row["source_system"],"source_term":row["source_term"],"source_type":row.get("source_type"),"source_identifier":row.get("source_identifier"),"provider":row.get("provider"),"entity_type":row.get("entity_type"),"concept_id":row["concept_id"],"confidence_score":row["confidence_score"],"mapping_strategy":row["mapping_strategy"],"explanation":row.get("explanation") or {},"attributes":plain_mapping(row.get("attributes",{}))}
        return MutableRecord(record_id=row["mapping_id"],organization_id=row["organization_id"],tenant_id=row["tenant_id"],created_at=dt(row["created_at"]),updated_at=dt(row["updated_at"]),schema_version=row.get("schema_version",1),metadata={"concept_id":row["concept_id"],"source_system":row["source_system"]},payload=p,revision=row.get("revision",1),active=row.get("active",True),deactivated_at=dt(row.get("deactivated_at")))
