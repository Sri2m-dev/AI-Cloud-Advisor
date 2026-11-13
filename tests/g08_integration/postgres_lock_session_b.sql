\set ON_ERROR_STOP on
DO $$
DECLARE
    lock_blocked boolean := false;
BEGIN
    PERFORM set_config('lock_timeout', '1500ms', true);
    PERFORM pg_sleep(2);
    BEGIN
        PERFORM public.g08_lock_identity_history();
        RAISE EXCEPTION 'global G08 transaction lock was not held by session A';
    EXCEPTION WHEN lock_not_available THEN
        lock_blocked := true;
    END;
    IF NOT lock_blocked THEN
        RAISE EXCEPTION 'concurrent session did not wait for the G08 transaction lock';
    END IF;
    RAISE NOTICE 'PASS: concurrent transaction was blocked by the G08 advisory lock';
END
$$;
