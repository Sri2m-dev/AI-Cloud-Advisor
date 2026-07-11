"""Supabase PostgreSQL append-only quality assessment repository adapter."""
from __future__ import annotations
from typing import Any
from data_fabric.adapters.supabase.client import SupabaseDataFabricClient
from data_fabric.adapters.supabase.exceptions import SupabaseAdapterOperationError
from data_fabric.adapters.supabase.repository_utils import apply_query_filters, dt, ensure_inserted, iso, optional_row, page_result, plain_mapping, response_rows
from data_fabric.foundation import TenantContext
from data_fabric.persistence.interfaces import QualityAssessmentRepository
from data_fabric.persistence.models import AppendOnlyRecord, ImmutableRecord, PageResult, RepositoryQuery

class SupabaseQualityAssessmentRepository(QualityAssessmentRepository):
    table_name="quality_assessments"
    def __init__(self, client: SupabaseDataFabricClient)->None: self.client=client
    def append(self, record: AppendOnlyRecord)->AppendOnlyRecord:
        row=self._record_to_row(record)
        response=self.client.execute(lambda:self.client.table(self.table_name).insert(row).execute())
        return self._row_to_record(ensure_inserted(response,"quality assessment"))
    def update(self, record: ImmutableRecord, *, expected_revision:int|None=None)->ImmutableRecord:
        raise SupabaseAdapterOperationError("quality_assessments is append-only and does not support update")
    def get(self, tenant_context:TenantContext, record_id:str, *, include_inactive:bool=False)->AppendOnlyRecord|None:
        response=self.client.execute(lambda:self._tenant_query(tenant_context).eq("assessment_id",record_id).limit(1).execute())
        row=optional_row(response); return self._row_to_record(row) if row else None
    def list_by_subject(self, tenant_context:TenantContext, subject_type:str, subject_id:str)->tuple[AppendOnlyRecord,...]:
        response=self.client.execute(lambda:self._tenant_query(tenant_context).eq("subject_type",subject_type).eq("subject_id",subject_id).order("assessed_at").execute())
        return tuple(self._row_to_record(r) for r in response_rows(response))
    def get_latest_by_subject(self, tenant_context:TenantContext, subject_type:str, subject_id:str)->AppendOnlyRecord|None:
        response=self.client.execute(lambda:self._tenant_query(tenant_context).eq("subject_type",subject_type).eq("subject_id",subject_id).order("assessed_at",desc=True).limit(1).execute())
        row=optional_row(response); return self._row_to_record(row) if row else None
    def find_by_decision(self, tenant_context:TenantContext, decision:str)->tuple[AppendOnlyRecord,...]:
        response=self.client.execute(lambda:self._tenant_query(tenant_context).eq("decision",decision).order("assessed_at").execute())
        return tuple(self._row_to_record(r) for r in response_rows(response))
    def find_below_score(self, tenant_context:TenantContext, max_score:float)->tuple[AppendOnlyRecord,...]:
        records=self.search(RepositoryQuery(tenant_context)).items
        return tuple(r for r in records if float(r.payload.get("overall_score",100.0)) < max_score)
    def exists(self, tenant_context:TenantContext, record_id:str)->bool: return self.get(tenant_context,record_id) is not None
    def count(self, query:RepositoryQuery)->int: return self.search(query).total_count
    def search(self, query:RepositoryQuery)->PageResult:
        response=self.client.execute(lambda:apply_query_filters(self._tenant_query(query.tenant_context),query).execute())
        return page_result([self._row_to_record(r) for r in response_rows(response)],query)
    def _tenant_query(self, tc:TenantContext): return self.client.table(self.table_name).select("*").eq("organization_id",tc.organization_id).eq("tenant_id",tc.tenant_id)
    def _record_to_row(self, record:AppendOnlyRecord)->dict[str,Any]:
        p=plain_mapping(record.payload); m=plain_mapping(record.metadata)
        return {"assessment_id":record.record_id,"subject_type":p.get("subject_type") or m.get("subject_type"),"subject_id":p.get("subject_id") or m.get("subject_id"),"organization_id":record.organization_id,"tenant_id":record.tenant_id,"overall_score":p.get("overall_score"),"trust_score":p.get("trust_score"),"decision":p.get("decision"),"dimensions":plain_mapping(p.get("dimensions",{})),"issues":p.get("issues",[]),"blocking_issues":p.get("blocking_issues",[]),"evaluator_version":p.get("evaluator_version"),"assessed_at":iso(dt(p.get("assessed_at")) or record.created_at),"metadata":plain_mapping(p.get("metadata",m)),"payload_hash":record.payload_hash,"schema_version":record.schema_version}
    def _row_to_record(self,row:dict[str,Any])->AppendOnlyRecord:
        payload={"subject_type":row["subject_type"],"subject_id":row["subject_id"],"overall_score":row["overall_score"],"trust_score":row.get("trust_score"),"decision":row.get("decision"),"dimensions":plain_mapping(row.get("dimensions",{})),"issues":row.get("issues") or [],"blocking_issues":row.get("blocking_issues") or [],"evaluator_version":row.get("evaluator_version"),"assessed_at":dt(row["assessed_at"]),"metadata":plain_mapping(row.get("metadata",{}))}
        return AppendOnlyRecord(record_id=row["assessment_id"],organization_id=row["organization_id"],tenant_id=row["tenant_id"],created_at=dt(row["assessed_at"]),updated_at=dt(row["assessed_at"]),schema_version=row.get("schema_version",1),metadata={"subject_type":row["subject_type"],"subject_id":row["subject_id"]},payload=payload,payload_hash=row.get("payload_hash") or "")
