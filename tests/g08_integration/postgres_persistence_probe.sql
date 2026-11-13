\set ON_ERROR_STOP on
SELECT current_database()
    || '|' || split_part(current_setting('server_version'), ' ', 1)
    || '|' || coalesce(to_regclass('public.g08_owner_operation_authorizations')::text, 'missing')
    || '|' || (SELECT count(*)::text FROM public.g08_owner_operation_authorizations)
    || '|' || coalesce(to_regclass('public.g08_d10_policy_versions')::text, 'missing')
    || '|' || (SELECT count(*)::text FROM public.g08_d10_policy_versions);
