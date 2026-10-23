#!/usr/bin/env bash
# Back up the database to one file.
#
#   DATABASE_URL=postgresql://user:pass@host:5432/dbname scripts/backup-db.sh [output-file]
#
# The app's own DATABASE_URL works as it is (the "+asyncpg" part is ignored). Needs pg_dump
# and pg_restore, version 17 or newer, on PATH: `apt install postgresql-client-17`, or run it
# inside the postgres container.
#
# The file is a "custom format" dump: compressed, restorable in part or whole with
# pg_restore, and written readable by you alone. A dump on the same server as the database
# is not a backup: copy it somewhere else (an object-storage bucket that is not the uploads
# bucket) straight after, and see docs/DEPLOYMENT.md for how often and how long to keep them.
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL (the database to back up)}"
url="${DATABASE_URL/+asyncpg/}"
out="${1:-alumni-$(date -u +%Y%m%dT%H%M%SZ).dump}"

umask 077
pg_dump --format=custom --no-owner --no-privileges --dbname "$url" --file "$out"

# A backup nobody has read back is a hope, not a backup. This proves the file is a valid
# archive and lists something in it.
entries="$(pg_restore --list "$out" | grep -c 'TABLE DATA' || true)"
if [ "$entries" -lt 1 ]; then
  echo "backup FAILED: $out contains no table data" >&2
  exit 1
fi
echo "backup written: $out ($(wc -c <"$out") bytes, $entries tables)"
