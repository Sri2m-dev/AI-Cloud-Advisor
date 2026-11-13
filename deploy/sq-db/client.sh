#!/bin/sh
set -eu
umask 077
mkdir -p /tmp/client
cp /run/secrets/pgpass /tmp/client/pgpass
chmod 600 /tmp/client/pgpass
exec psql "$@"
