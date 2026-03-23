"""
Database service for users and preferences.

This module is the canonical place for:
- ensuring a user exists on login
- reading user profile (+ preferences)
- updating user profile and preferences

All DB calls go through core.db helpers to ensure consistent error reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import asyncpg

from src.api.core import db as db_core


@dataclass(frozen=True)
class ProfileRecord:
    """Internal representation of a user's profile + preferences."""

    user_id: str
    username: str
    full_name: Optional[str]
    email: Optional[str]
    theme: str


async def ensure_user_exists(pool: asyncpg.Pool, username: str) -> ProfileRecord:
    """
    Ensure a user row exists (and preferences row exists), returning profile.

    Contract:
    - Creates a user if missing.
    - Ensures a preferences row exists with default theme 'dark'.
    """
    row = await db_core.fetchrow(
        pool,
        "users.ensure_user",
        """
        INSERT INTO users (username)
        VALUES ($1)
        ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
        RETURNING id::text AS id, username, full_name, email;
        """,
        username,
    )
    assert row is not None  # insert/returning should always return a row

    await db_core.execute(
        pool,
        "preferences.ensure_default",
        """
        INSERT INTO user_preferences (user_id, theme)
        VALUES ($1::uuid, 'dark')
        ON CONFLICT (user_id) DO NOTHING;
        """,
        row["id"],
    )

    return await get_profile_by_username(pool, username)


async def get_profile_by_username(pool: asyncpg.Pool, username: str) -> ProfileRecord:
    """Load profile + preferences for a username, raising if missing."""
    row = await db_core.fetchrow(
        pool,
        "profile.get_by_username",
        """
        SELECT
            u.id::text AS id,
            u.username,
            u.full_name,
            u.email,
            COALESCE(p.theme, 'dark') AS theme
        FROM users u
        LEFT JOIN user_preferences p ON p.user_id = u.id
        WHERE u.username = $1;
        """,
        username,
    )
    if row is None:
        raise ValueError(f"User not found: {username}")

    return ProfileRecord(
        user_id=row["id"],
        username=row["username"],
        full_name=row["full_name"],
        email=row["email"],
        theme=row["theme"],
    )


async def update_settings(
    pool: asyncpg.Pool,
    username: str,
    *,
    name: Optional[str],
    email: Optional[str],
    theme: Optional[str],
) -> ProfileRecord:
    """
    Update user profile and/or preferences.

    Contract:
    - If name/email/theme are None, those fields are not changed.
    - Returns the updated profile.
    """
    profile = await get_profile_by_username(pool, username)

    if name is not None or email is not None:
        await db_core.fetchrow(
            pool,
            "users.update_profile",
            """
            UPDATE users
            SET
              full_name = COALESCE($2, full_name),
              email = COALESCE($3, email)
            WHERE id = $1::uuid
            RETURNING id;
            """,
            profile.user_id,
            name,
            email,
        )

    if theme is not None:
        await db_core.execute(
            pool,
            "preferences.upsert_theme",
            """
            INSERT INTO user_preferences (user_id, theme)
            VALUES ($1::uuid, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET theme = EXCLUDED.theme, updated_at = now();
            """,
            profile.user_id,
            theme,
        )

    return await get_profile_by_username(pool, username)
