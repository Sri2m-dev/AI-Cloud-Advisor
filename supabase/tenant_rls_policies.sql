-- Tenant isolation RLS policies
-- Safe for mixed schemas where tenant key can be org_id or tenant_id.
-- Apply in Supabase SQL editor.

do $$
declare
	tbl text;
	tenant_col text;
	policy_name text;
	tenant_expr text;
begin
	foreach tbl in array[
		'unified_cloud_costs',
		'recommendations',
		'mart_cost_anomalies',
		'kpi_total_cloud_spend',
		'kpi_anomaly_summary',
		'kpi_optimization_summary',
		'kpi_spend_by_cloud',
		'kpi_top_services'
	]
	loop
		if to_regclass(format('public.%I', tbl)) is null then
			raise notice 'Skipping %. Table does not exist.', tbl;
			continue;
		end if;

		if exists (
			select 1
			from information_schema.columns
			where table_schema = 'public'
			  and table_name = tbl
			  and column_name = 'org_id'
		) then
			tenant_col := 'org_id';
			tenant_expr := '(org_id::text = coalesce(auth.jwt()->>''tenant_id'', auth.jwt()->>''org_id''))';
		elsif exists (
			select 1
			from information_schema.columns
			where table_schema = 'public'
			  and table_name = tbl
			  and column_name = 'tenant_id'
		) then
			tenant_col := 'tenant_id';
			tenant_expr := '(tenant_id::text = coalesce(auth.jwt()->>''tenant_id'', auth.jwt()->>''org_id''))';
		else
			raise notice 'Skipping %. Neither org_id nor tenant_id exists.', tbl;
			continue;
		end if;

		execute format('alter table public.%I enable row level security', tbl);

		policy_name := format('tenant_isolation_%s', tbl);
		execute format('drop policy if exists %I on public.%I', policy_name, tbl);

		execute format(
			'create policy %I on public.%I for all using (%s) with check (%s)',
			policy_name,
			tbl,
			tenant_expr,
			tenant_expr
		);

		raise notice 'Applied RLS on %. Using %.', tbl, tenant_col;
	end loop;
end
$$;
