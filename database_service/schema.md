# Beacon-Safe Database Schema (minimal)

This Postgres instance is used for persistence of **user profile** and **system preferences** (currently: theme).

## Tables

### `users`
- `id` (uuid, PK, default `gen_random_uuid()`)
- `username` (text, UNIQUE, required)
- `full_name` (text, nullable)
- `email` (text, nullable)
- `created_at` (timestamptz, default `now()`)

### `user_preferences`
- `user_id` (uuid, PK, FK -> `users(id)` ON DELETE CASCADE)
- `theme` (text, default `'dark'`, constraint: `'light'` or `'dark'`)
- `updated_at` (timestamptz, default `now()`)

## Seed (dev)
Creates/updates a `demo` user and sets theme to `dark`.
