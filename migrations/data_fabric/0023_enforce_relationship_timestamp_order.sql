-- P3 Data Fabric migration 0023
-- Purpose: normalize persistence audit time before the relationship order constraint.
-- Effective business dates remain unchanged.

create or replace function data_fabric.normalize_relationship_audit_timestamps()
returns trigger
language plpgsql
set search_path = data_fabric, pg_temp
as $$
begin
    new.updated_at := greatest(new.created_at, coalesce(new.updated_at, new.created_at));
    return new;
end;
$$;

 drop trigger if exists enterprise_relationships_timestamp_order_trigger
    on data_fabric.enterprise_relationships;

create trigger enterprise_relationships_timestamp_order_trigger
before insert or update on data_fabric.enterprise_relationships
for each row
execute function data_fabric.normalize_relationship_audit_timestamps();
