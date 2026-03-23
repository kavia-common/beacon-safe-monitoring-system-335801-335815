from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.core.db import (
    DatabaseOperationError,
    close_db_pool,
    create_db_pool,
    load_postgres_dsn_from_db_connection_file,
)
from src.api.routers import auth as auth_router
from src.api.routers import devices as devices_router
from src.api.routers import me as me_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("beacon_safe.backend")


openapi_tags = [
    {"name": "Authentication", "description": "Mock authentication endpoints."},
    {"name": "Devices", "description": "Dashboard device inventory (demo data)."},
    {"name": "Account", "description": "Profile and preference APIs backed by Postgres."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    App lifecycle.

    - Reads Postgres DSN from db_connection.txt (repo convention).
    - Creates a connection pool and stores it on app.state.db_pool.

    If DSN parsing or connection fails, the app will still start but protected
    endpoints will return 503 with diagnostic context via DatabaseOperationError.
    """
    try:
        dsn = load_postgres_dsn_from_db_connection_file()
        app.state.db_pool = await create_db_pool(dsn)
        logger.info("db.pool.ready")
    except Exception as exc:  # noqa: BLE001
        # Keep app alive for health checks/docs; surface DB failures per-request.
        app.state.db_pool = None
        logger.exception("db.pool.failed: %s", exc)

    try:
        yield
    finally:
        pool = getattr(app.state, "db_pool", None)
        if pool is not None:
            await close_db_pool(pool)
            logger.info("db.pool.closed")


app = FastAPI(
    title="Beacon-Safe Backend API",
    description="FastAPI backend for the Beacon-Safe monitoring console (mock auth + devices + profile/preferences).",
    version="1.0.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

def _split_csv_env(name: str, default: list[str]) -> list[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]

allowed_origins = _split_csv_env("ALLOWED_ORIGINS", ["http://localhost:3000"])
allowed_methods = _split_csv_env(
    "ALLOWED_METHODS",
    ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
allowed_headers = _split_csv_env(
    "ALLOWED_HEADERS",
    ["Content-Type", "Authorization"],
)
cors_max_age = int((os.getenv("CORS_MAX_AGE") or "600").strip() or "600")

app.add_middleware(
    CORSMiddleware,
    # NOTE: Avoid allow_origins=["*"] with allow_credentials=True (browsers reject it).
    allow_origins=allowed_origins,
    # Token-based auth (Authorization header) does not require credentials.
    # Can be enabled via env later if cookies are introduced.
    allow_credentials=False,
    allow_methods=allowed_methods,
    allow_headers=allowed_headers,
    max_age=cors_max_age,
)


@app.exception_handler(DatabaseOperationError)
async def handle_db_error(_: Request, exc: DatabaseOperationError) -> JSONResponse:
    """Consistent DB failure mapping for all endpoints."""
    logger.exception(
        "db.operation.failed operation=%s detail=%s error=%r",
        exc.operation,
        exc.detail,
        exc.original_exception,
    )
    return JSONResponse(
        status_code=503,
        content={
            "message": "Database unavailable",
            "operation": exc.operation,
            "detail": exc.detail,
        },
    )


@app.get("/", tags=["Account"], summary="Health check", operation_id="health_check")
# PUBLIC_INTERFACE
def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
    - {"message": "Healthy"}
    """
    return {"message": "Healthy"}


# Routers
app.include_router(auth_router.router)
app.include_router(devices_router.router)
app.include_router(me_router.router)
