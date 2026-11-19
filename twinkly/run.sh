#!/bin/sh
set -eu

# Reconcile the Supervisor's data mount and existing backups on startup.
find -P /data -xdev \( ! -user twinkly -o ! -group twinkly \) -exec chown -h twinkly:twinkly {} +
export HOME=/data
umask 077
exec setpriv --reuid=twinkly --regid=twinkly --clear-groups \
    --inh-caps=-all --ambient-caps=-all --no-new-privs -- "$@"
