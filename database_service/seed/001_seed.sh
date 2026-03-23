#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-5432}"

psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d beacon_safe -c "INSERT INTO users (username, full_name, email) VALUES ('demo', 'Demo User', 'demo@beacon-safe.local') ON CONFLICT (username) DO UPDATE SET full_name = EXCLUDED.full_name, email = EXCLUDED.email;"

psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -p "${PORT}" -d beacon_safe -c "INSERT INTO user_preferences (user_id, theme) VALUES ((SELECT id FROM users WHERE username='demo'), 'dark') ON CONFLICT (user_id) DO UPDATE SET theme = EXCLUDED.theme, updated_at = now();"
