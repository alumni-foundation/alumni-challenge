#!/usr/bin/env bash
# Restore a backup made by scripts/backup-db.sh.
#
#   scripts/restore-db.sh <dump-file> <target-database-url> [--yes-overwrite]
#
# The target database must already exist (`createdb`, or CREATE DATABASE). It must be empty
# unless you pass --yes-overwrite, which replaces what is there. To rehearse a restore, point
# it at a NEW database, never at the live one.
#
# After a restore, start the app's migration command once: it brings the schema to the latest
# version if the backup was older than the code.
set -euo pipefail

dump="${1:?usage: restore-db.sh <dump-file> <target-database-url> [--yes-overwrite]}"
target="${2:?usage: restore-db.sh <dump-file> <target-database-url> [--yes-overwrite]}"
overwrite="${3:-}"
target="${target/+asyncpg/}"

[ -f "$dump" ] || { echo "no such file: $dump" >&2; exit 1; }
pg_restore --list "$dump" >/dev/null || { echo "not a valid backup file: $dump" >&2; exit 1; }

existing="$(psql "$target" -Atc "select count(*) from pg_tables where schemaname = 'public'")"
if [ "$existing" -gt 0 ] && [ "$overwrite" != "--yes-overwrite" ]; then
  echo "refusing: the target already has $existing tables." >&2
  echo "Restore into an empty database, or pass --yes-overwrite if you mean to replace it." >&2
  exit 1
fi

flags=(--no-owner --no-privileges --exit-on-error)
if [ "$overwrite" = "--yes-overwrite" ]; then
  flags+=(--clean --if-exists)
fi
pg_restore "${flags[@]}" --dbname "$target" "$dump"

echo "restored. Tables and rows:"
psql "$target" -Atc "
  select format('  %-28s %s', relname, n_live_tup)
  from pg_stat_user_tables order by relname"
echo "schema version: $(psql "$target" -Atc 'select version_num from alembic_version')"
