-- Explicit local disposable safety interlock; not itself environment authorization.
DO $$ BEGIN
 IF current_setting('nexora.qualification_authorized',true) IS DISTINCT FROM 'local-disposable'
  OR current_database() NOT LIKE 'nexora_m2c_%'
  OR (inet_server_addr() IS NOT NULL AND inet_server_addr() NOT IN ('127.0.0.1'::inet,'::1'::inet)) THEN
  RAISE EXCEPTION 'explicit authorized local disposable fixture required';
 END IF;
END $$;
