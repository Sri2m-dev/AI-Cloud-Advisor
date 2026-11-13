#!/bin/sh
set -eu
umask 077
password=$(cat /run/secrets/redis_password)
monitor_password=$(cat /run/secrets/redis_monitor_password)
case "$password" in
  ''|*[!A-Za-z0-9]*) echo 'Managed Redis password must be nonempty high-entropy alphanumeric material' >&2; exit 78 ;;
esac
[ "${#password}" -ge 32 ] || exit 78
case "$monitor_password" in ''|*[!A-Za-z0-9]*) exit 78 ;; esac
[ "${#monitor_password}" -ge 32 ] || exit 78
[ "$password" != "$monitor_password" ] || exit 78
printf 'appendonly yes\nprotected-mode yes\ndir /data\nrequirepass %s\nuser monitor on >%s -@all +ping\n' "$password" "$monitor_password" > /tmp/redis.conf
unset password monitor_password
exec redis-server /tmp/redis.conf
