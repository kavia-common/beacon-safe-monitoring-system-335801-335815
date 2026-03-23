#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-5432}"

psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d beacon_safe -c "CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"

psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d beacon_safe -c "CREATE TABLE IF NOT EXISTS users (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), username text NOT NULL UNIQUE, full_name text, email text, created_at timestamptz NOT NULL DEFAULT now());"

psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d beacon_safe -c "CREATE TABLE IF NOT EXISTS user_preferences (user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, theme text NOT NULL DEFAULT 'dark' CHECK (theme IN ('light','dark')), updated_at timestamptz NOT NULL DEFAULT now());"

psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d beacon_safe -c "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);"
