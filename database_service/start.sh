#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-5432}"
HOST="${2:-0.0.0.0}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PGDATA="$BASE_DIR/pgdata"
LOGFILE="$BASE_DIR/postgres.log"

# Find postgres server binaries (Debian/Ubuntu layout)
PG_BINDIR="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -n 1 || true)"
if [[ -z "${PG_BINDIR}" ]]; then
  echo "ERROR: Postgres server binaries not found under /usr/lib/postgresql/*/bin." >&2
  echo "Ensure the container build/install step installed: postgresql postgresql-contrib" >&2
  exit 1
fi
export PATH="${PG_BINDIR}:${PATH}"

mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"

if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
  echo "Initializing Postgres data directory at: $PGDATA"
  runuser -u postgres -- initdb -D "$PGDATA" -U postgres --auth=trust >/dev/null

  # Make the instance accessible in dev (deterministic, not for production).
  echo "listen_addresses = '*'" >> "$PGDATA/postgresql.conf"
  echo "port = ${PORT}" >> "$PGDATA/postgresql.conf"
  echo "host all all 0.0.0.0/0 trust" >> "$PGDATA/pg_hba.conf"
  echo "host all all ::/0 trust" >> "$PGDATA/pg_hba.conf"
fi

echo "Starting Postgres briefly to apply migrations/seed..."
runuser -u postgres -- pg_ctl -D "$PGDATA" -o "-h 0.0.0.0 -p ${PORT}" -w start -l "$LOGFILE"

# Create app role + database (idempotent).
runuser -u postgres -- psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'beacon_safe') THEN CREATE ROLE beacon_safe LOGIN; END IF; END \$\$;"
runuser -u postgres -- psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'beacon_safe') THEN CREATE DATABASE beacon_safe OWNER beacon_safe; END IF; END \$\$;"

# Run migrations (idempotent scripts).
shopt -s nullglob
for f in "$BASE_DIR"/migrations/*.sh; do
  echo "Running migration: $(basename "$f")"
  runuser -u postgres -- bash "$f" "${PORT}"
done

# Run seeds (idempotent scripts).
for f in "$BASE_DIR"/seed/*.sh; do
  echo "Running seed: $(basename "$f")"
  runuser -u postgres -- bash "$f" "${PORT}"
done
shopt -u nullglob

echo "Stopping temporary Postgres..."
runuser -u postgres -- pg_ctl -D "$PGDATA" -m fast -w stop

echo "Starting Postgres in foreground on ${HOST}:${PORT}"
exec runuser -u postgres -- postgres -D "$PGDATA" -h "${HOST}" -p "${PORT}"
