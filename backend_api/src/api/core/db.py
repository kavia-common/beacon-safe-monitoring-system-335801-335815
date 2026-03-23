"""
Database adapter layer for Beacon-Safe (Postgres).

Uses the repository convention:
- Read Postgres DSN from backend_api/db_connection.txt, which contains a command like:
  `psql postgresql://user@host:port/db`

This module provides:
- a single pool lifecycle entrypoint
- safe helpers that wrap asyncpg errors in a structured exception so the API
  layer can map failures consistently.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import asyncpg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatabaseOperationError(RuntimeError):
    """Raised when a database operation fails, preserving operation context."""

    operation: str
    detail: str
    original_exception: BaseException


# PUBLIC_INTERFACE
def load_postgres_dsn_from_db_connection_file(db_connection_path: Optional[Path] = None) -> str:
    """
    Load a Postgres DSN using the db_connection.txt convention.

    Contract:
    - Input:
      - db_connection_path: Optional explicit path to db_connection.txt.
        If omitted, resolves backend_api/db_connection.txt relative to this file.
    - Output:
      - A DSN string acceptable to asyncpg, e.g. postgresql://user@host:port/db
    - Errors:
      - ValueError if the file is missing or cannot be parsed.
    - Side effects:
      - Reads a local text file.
    """
    if db_connection_path is None:
        # .../backend_api/src/api/core/db.py -> parents[3] == backend_api/
        backend_root = Path(__file__).resolve().parents[3]
        db_connection_path = backend_root / "db_connection.txt"

    try:
        raw = db_connection_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise ValueError(
            f"db_connection.txt not found at {db_connection_path}. "
            "Backend requires this file to connect to Postgres."
        ) from exc

    if not raw:
        raise ValueError(f"db_connection.txt at {db_connection_path} is empty.")

    # Common convention: "psql postgresql://...."
    if raw.startswith("psql "):
        dsn = raw[len("psql ") :].strip()
    else:
        # Accept DSN-only content as a fallback for other environments.
        dsn = raw.strip()

    if not (dsn.startswith("postgresql://") or dsn.startswith("postgres://")):
        raise ValueError(
            f"Invalid DSN parsed from {db_connection_path}. "
            f"Expected postgres DSN, got: {dsn!r}"
        )

    return dsn


# PUBLIC_INTERFACE
async def create_db_pool(dsn: str) -> asyncpg.Pool:
    """
    Create an asyncpg connection pool.

    Contract:
    - Input: postgresql DSN string
    - Output: asyncpg.Pool
    - Errors: raises DatabaseOperationError if connection fails
    - Side effects: opens network connections to Postgres
    """
    try:
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )
        return pool
    except Exception as exc:  # noqa: BLE001 - add context + rethrow as structured error
        raise DatabaseOperationError(
            operation="db.create_pool",
            detail="Failed to connect to Postgres. Ensure database_service is running and DSN is correct.",
            original_exception=exc,
        ) from exc


async def close_db_pool(pool: asyncpg.Pool) -> None:
    """Close an asyncpg pool safely."""
    await pool.close()


async def fetchrow(pool: asyncpg.Pool, operation: str, query: str, *args: Any) -> Optional[asyncpg.Record]:
    """Fetch a single row and wrap failures with operation context."""
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    except Exception as exc:  # noqa: BLE001
        raise DatabaseOperationError(
            operation=operation,
            detail="Database fetchrow failed.",
            original_exception=exc,
        ) from exc


async def fetch(pool: asyncpg.Pool, operation: str, query: str, *args: Any) -> list[asyncpg.Record]:
    """Fetch multiple rows and wrap failures with operation context."""
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return list(rows)
    except Exception as exc:  # noqa: BLE001
        raise DatabaseOperationError(
            operation=operation,
            detail="Database fetch failed.",
            original_exception=exc,
        ) from exc


async def execute(pool: asyncpg.Pool, operation: str, query: str, *args: Any) -> str:
    """Execute a statement and wrap failures with operation context."""
    try:
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
    except Exception as exc:  # noqa: BLE001
        raise DatabaseOperationError(
            operation=operation,
            detail="Database execute failed.",
            original_exception=exc,
        ) from exc
