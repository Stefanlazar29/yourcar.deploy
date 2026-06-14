#!/bin/sh
set -eu
INTERVAL="${BACKUP_INTERVAL_SEC:-3600}"
echo "[backup_loop] interval=${INTERVAL}s"
while true; do
  python3 /scripts/mulberry_backup.py || true
  sleep "$INTERVAL"
done
