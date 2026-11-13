#!/bin/sh
set -eu
# Materialize restrictive Linux permissions on tmpfs; never alter source secrets.
umask 077
cp /run/secrets/server_cert /run/sqdb/server.crt
cp /run/secrets/server_key /run/sqdb/server.key
chown postgres:postgres /run/sqdb/server.crt /run/sqdb/server.key
chmod 600 /run/sqdb/server.crt /run/sqdb/server.key
exec /usr/local/bin/docker-entrypoint.sh "$@"
