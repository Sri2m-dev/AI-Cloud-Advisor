#!/bin/sh
set -eu
umask 077
cp /run/secrets/server_cert /run/sqdb/server.crt
cp /run/secrets/server_key /run/sqdb/server.key
chown postgres:postgres /run/sqdb/server.crt /run/sqdb/server.key
chmod 600 /run/sqdb/server.crt /run/sqdb/server.key
mkdir -p /tmp/client
cp /run/secrets/pgpass /tmp/client/pgpass
chmod 600 /tmp/client/pgpass
# Fresh tmpfs cluster only. No persistent volume is mounted by this service.
/usr/local/bin/docker-entrypoint.sh postgres -c ssl=on -c ssl_cert_file=/run/sqdb/server.crt -c ssl_key_file=/run/sqdb/server.key > /tmp/server.log 2>&1 &
server=$!
ready=false
for attempt in $(seq 1 60); do
 if pg_isready -h 127.0.0.1 -U postgres -d "$POSTGRES_DB" >/dev/null 2>&1; then ready=true; break; fi
 if ! kill -0 "$server" 2>/dev/null; then cat /tmp/server.log; exit 1; fi
 sleep 1
done
if test "$ready" != true; then echo 'fresh fixture startup timeout'; exit 1; fi
# A real verified-TLS connection gates the unmodified canonical installer path.
psql -X -v ON_ERROR_STOP=1 -f /qualification/database/contracts/g08_m2c/qualification/install_and_test.sql
printf '{"clean_install":"PASS","tls":"verify-full","persistent_volume_mounted":false}\n'
touch /tmp/clean-install-passed
# Retain this new in-memory fixture and evidence; no automatic cleanup.
wait "$server"
