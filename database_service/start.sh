#!/usr/bin/env bash
set -euo pipefail

# Beacon-Safe database bootstrap + runtime
#
# Contract:
# - Starts a Postgres server that listens on the requested port and is reachable from outside the container.
# - Initializes PGDATA on first run (idempotent).
# - Applies migrations + seed after Postgres is accepting connections (idempotent scripts).
#
# Why this shape:
# - `initdb` and `postgres` refuse to run as root. Preview environments may run containers as root OR non-root.
#   We therefore drop privileges to the OS `postgres` user only when running as root, while keeping non-root
#   compatibility (no mandatory `runuser` usage).
# - We start Postgres once (no stop/restart) to avoid readiness flakiness during startup.

PORT="${1:-5432}"
# HOST is intentionally not used to bind because preview health checks and dependent containers need external binding.
# Binding is controlled via postgresql.conf (`listen_addresses='*'`).
HOST="${2:-0.0.0.0}"

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PGDATA="${BASE_DIR}/pgdata"
LOGFILE="${PGDATA}/postgres.log"

# Find postgres server binaries (Debian/Ubuntu layout)
PG_BINDIR="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -n 1 || true)"
if [[ -z "${PG_BINDIR}" ]]; then
  echo "ERROR: Postgres server binaries not found under /usr/lib/postgresql/*/bin." >&2
  echo "Ensure the container build/install step installed: postgresql postgresql-contrib" >&2
  exit 1
fi

INITDB_BIN="${PG_BINDIR}/initdb"
POSTGRES_BIN="${PG_BINDIR}/postgres"
PG_ISREADY_BIN="${PG_BINDIR}/pg_isready"

# Run a command as the OS 'postgres' user only when we're root.
run_as_pg() {
  if [[ "$(id -u)" -eq 0 ]]; then
    if command -v runuser >/dev/null 2>&1; then
      runuser -u postgres -- "$@"
      return
    fi
    if command -v su >/dev/null 2>&1; then
      # shellcheck disable=SC2016
      su -s /bin/bash postgres -c "$(printf '%q ' "$@")"
      return
    fi
    echo "ERROR: running as root but neither 'runuser' nor 'su' is available to drop privileges." >&2
    exit 1
  fi

  "$@"
}

on_error() {
  local exit_code=$?
  echo "ERROR: database_service start.sh failed (exit=${exit_code})." >&2
  if [[ -f "${LOGFILE}" ]]; then
    echo "---- Last 200 lines of ${LOGFILE} ----" >&2
    tail -n 200 "${LOGFILE}" >&2 || true
    echo "---- End log ----" >&2
  fi
  exit "${exit_code}"
}
trap on_error ERR

# Ensure PGDATA exists and is writable by the effective Postgres OS user.
mkdir -p "${PGDATA}"
chmod 700 "${PGDATA}" || true
if [[ "$(id -u)" -eq 0 ]]; then
  # When running as root we will run Postgres as OS user 'postgres',
  # so ownership must be correct for initdb/postgres to write.
  chown -R postgres:postgres "${PGDATA}" || true
fi

ensure_line_in_file() {
  local file="$1"
  local line="$2"
  grep -Fqx "${line}" "${file}" 2>/dev/null || echo "${line}" >>"${file}"
}

if [[ ! -f "${PGDATA}/PG_VERSION" ]]; then
  echo "Initializing Postgres data directory at: ${PGDATA}"
  # NOTE: Do not run initdb as root; it will fail. We drop privileges conditionally via run_as_pg.
  run_as_pg "${INITDB_BIN}" -D "${PGDATA}" -U postgres --auth=trust >/dev/null

  # Deterministic dev config (NOT for production).
  ensure_line_in_file "${PGDATA}/postgresql.conf" "listen_addresses = '*'"
  ensure_line_in_file "${PGDATA}/postgresql.conf" "port = ${PORT}"
  ensure_line_in_file "${PGDATA}/pg_hba.conf" "host all all 0.0.0.0/0 trust"
  ensure_line_in_file "${PGDATA}/pg_hba.conf" "host all all ::/0 trust"
else
  # If PGDATA already exists (e.g., after a rebuild), ensure it still binds externally on the requested port.
  ensure_line_in_file "${PGDATA}/postgresql.conf" "listen_addresses = '*'"
  ensure_line_in_file "${PGDATA}/postgresql.conf" "port = ${PORT}"
  ensure_line_in_file "${PGDATA}/pg_hba.conf" "host all all 0.0.0.0/0 trust"
  ensure_line_in_file "${PGDATA}/pg_hba.conf" "host all all ::/0 trust"
fi

mkdir -p "$(dirname "${LOGFILE}")"

echo "Starting Postgres (expected to listen on 0.0.0.0:${PORT})"
# Start postgres in background so we can bootstrap schema while keeping port open (readiness-friendly).
run_as_pg "${POSTGRES_BIN}" -D "${PGDATA}" -p "${PORT}" >>"${LOGFILE}" 2>&1 &
POSTGRES_WRAPPER_PID=$!

# Wait for readiness
echo "Waiting for Postgres to accept connections..."
for _ in $(seq 1 120); do
  if run_as_pg "${PG_ISREADY_BIN}" -h 127.0.0.1 -p "${PORT}" -U postgres -d postgres >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! run_as_pg "${PG_ISREADY_BIN}" -h 127.0.0.1 -p "${PORT}" -U postgres -d postgres >/dev/null 2>&1; then
  echo "ERROR: Postgres did not become ready on port ${PORT}." >&2
  exit 1
fi

echo "Postgres is ready. Applying migrations + seed..."

# Create app role + database (idempotent).
psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -U postgres -d postgres -c \
  "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'beacon_safe') THEN CREATE ROLE beacon_safe LOGIN; END IF; END \$\$;"
psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -U postgres -d postgres -c \
  "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'beacon_safe') THEN CREATE DATABASE beacon_safe OWNER beacon_safe; END IF; END \$\$;"

# Run migrations (idempotent scripts).
shopt -s nullglob
for f in "${BASE_DIR}"/migrations/*.sh; do
  echo "Running migration: $(basename "${f}")"
  bash "${f}" "${PORT}"
done

# Run seeds (idempotent scripts).
for f in "${BASE_DIR}"/seed/*.sh; do
  echo "Running seed: $(basename "${f}")"
  bash "${f}" "${PORT}"
done
shopt -u nullglob

echo "Bootstrap complete. Postgres running; waiting on server process."
wait "${POSTGRES_WRAPPER_PID}"
