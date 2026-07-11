-- P3 Data Fabric migration 0001
-- Purpose: create isolated Data Fabric schema.
-- Safety: non-destructive; no data changes; no credentials.

create schema if not exists data_fabric;

comment on schema data_fabric is 'P3 Enterprise Data Fabric canonical persistence schema';
