"""Supabase PostgreSQL idempotency repository adapter."""
from __future__ import annotations
from typing import Any
from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterConflictError
from data_fabric.adapters.supabase.repository_utils import apply_query_filters, dt, optional_row, page_result, plain_mapping, response_rows
from data_fabric.foundation import TenantContext
from data_fabric.orchestration import IdempotencyState
from data_fabric.persistence.interfaces import IdempotencyRepository
from data_fabric.persistence.models import MutableRecord, PageResult, RepositoryQuery

class SupabaseIdempotencyRepository(IdempotencyRepository):
    table_name="idempotency_records"
    def __init__(self, client:SupabaseDataFabricClient)->None: self.client=client
    def add(self, record:MutableRecord)->MutableRecord: return self.reserve(record.tenant_context, str(record.metadata.get("idempotency_key") or record.record_id), str(record.payload.get("payload_hash")))
    def update(self, record:MutableRecord, *, expected_revision:int)->MutableRecord: raise SupabaseAdapterConflictError("idempotency updates must use explicit state transition methods")
    def deactivate(self, tenant_context:TenantContext, record_id:str, *, deactivated_by:str|None=None)->MutableRecord: raise SupabaseAdapterConflictError("idempotency records do not support deactivate")
    def reserve_key(self, tenant_context:TenantContext, key:str, payload_hash:str)->MutableRecord: return self.reserve(tenant_context,key,payload_hash)
    def reserve(self, tenant_context:TenantContext, key:str, payload_hash:str, *, correlation_id:str|None=None, expires_at:Any=None)->MutableRecord:
        rows=response_rows(self.client.execute(lambda:self.client.rpc("data_fabric_reserve_idempotency_key",{"p_organization_id":tenant_context.organization_id,"p_tenant_id":tenant_context.tenant_id,"p_idempotency_key":key,"p_payload_hash":payload_hash,"p_correlation_id":correlation_id,"p_expires_at":expires_at})))
        if not rows: raise SupabaseAdapterConflictError("idempotency key conflict")
        return self._row_to_record(rows[0])
    def get(self, tc:TenantContext, record_id:str, *, include_inactive:bool=False)->MutableRecord|None:
        row=optional_row(self.client.execute(lambda:self._tenant_query(tc).eq("idempotency_key",record_id).limit(1).execute()))
        return self._row_to_record(row) if row else None
    def compare_payload_hash(self, tc:TenantContext, key:str, payload_hash:str)->bool:
        record=self.get(tc,key); return bool(record and record.payload.get("payload_hash")==payload_hash)
    def mark_completed(self, tc:TenantContext, key:str, result_ref:str)->MutableRecord:
        return self._transition("data_fabric_complete_idempotency_key",tc,key,{"p_result_payload":{"result_ref":result_ref}})
    def mark_failed(self, tc:TenantContext, key:str, reason:str)->MutableRecord:
        return self._transition("data_fabric_fail_idempotency_key",tc,key,{"p_failure_reason":reason})
    def mark_expired(self, tc:TenantContext, key:str)->MutableRecord:
        return self._transition("data_fabric_expire_idempotency_key",tc,key,{})
    def get_status(self, tc:TenantContext, key:str)->IdempotencyState|None:
        record=self.get(tc,key); return IdempotencyState(record.payload["status"]) if record else None
    def list_by_status(self, tc:TenantContext, status:IdempotencyState|str)->tuple[MutableRecord,...]:
        response=self.client.execute(lambda:self._tenant_query(tc).eq("status",str(status.value if isinstance(status,IdempotencyState) else status)).order("reserved_at").execute())
        return tuple(self._row_to_record(r) for r in response_rows(response))
    def exists(self,tc:TenantContext,record_id:str)->bool: return self.get(tc,record_id) is not None
    def count(self,query:RepositoryQuery)->int: return self.search(query).total_count
    def search(self,query:RepositoryQuery)->PageResult:
        response=self.client.execute(lambda:apply_query_filters(self._tenant_query(query.tenant_context),query).execute())
        return page_result([self._row_to_record(r) for r in response_rows(response)],query)
    def _transition(self, fn:str, tc:TenantContext, key:str, extra:dict[str,Any])->MutableRecord:
        params={"p_organization_id":tc.organization_id,"p_tenant_id":tc.tenant_id,"p_idempotency_key":key}|extra
        rows=response_rows(self.client.execute(lambda:self.client.rpc(fn,params)))
        if not rows: raise SupabaseAdapterConflictError("invalid idempotency state transition")
        return self._row_to_record(rows[0])
    def _tenant_query(self,tc): return self.client.table(self.table_name).select("*").eq("organization_id",tc.organization_id).eq("tenant_id",tc.tenant_id)
    def _row_to_record(self,row:dict[str,Any])->MutableRecord:
        payload={"idempotency_key":row["idempotency_key"],"payload_hash":row["payload_hash"],"status":row["status"],"result_payload":plain_mapping(row.get("result_payload",{})),"failure_reason":row.get("failure_reason"),"reserved_at":dt(row["reserved_at"]),"completed_at":dt(row.get("completed_at")),"failed_at":dt(row.get("failed_at")),"expires_at":dt(row.get("expires_at")),"correlation_id":row.get("correlation_id"),"metadata":plain_mapping(row.get("metadata",{}))}
        return MutableRecord(record_id=row["idempotency_key"],organization_id=row["organization_id"],tenant_id=row["tenant_id"],created_at=dt(row["reserved_at"]),updated_at=dt(row.get("completed_at") or row.get("failed_at") or row["reserved_at"]),schema_version=row.get("schema_version",1),metadata={"idempotency_key":row["idempotency_key"]},payload=payload,revision=row.get("revision",1),active=True)
