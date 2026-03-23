from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.core.auth import issue_mock_token
from src.api.core.db import DatabaseOperationError
from src.api.schemas import LoginRequest, LoginResponse, UserOut
from src.api.services.user_service import ensure_user_exists

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Mock login (accepts any credentials)",
    operation_id="auth_login",
)
# PUBLIC_INTERFACE
async def login(payload: LoginRequest, request: Request) -> JSONResponse:
    """
    Authenticate a user (mock).

    Contract:
    - Accepts any username/password.
    - Ensures the user exists in Postgres (creating rows if needed).
    - Returns a mock Bearer token encoding the username plus a user object.

    Parameters:
    - payload: LoginRequest (username, password)

    Returns:
    - LoginResponse { token, user }
    """
    pool = request.app.state.db_pool
    if pool is None:
        raise DatabaseOperationError(
            operation="db.pool.unavailable",
            detail="Database pool not initialized. Ensure database_service is running.",
            original_exception=RuntimeError("app.state.db_pool is None"),
        )
    profile = await ensure_user_exists(pool, payload.username.strip())
    token = issue_mock_token(profile.username)

    return JSONResponse(
        LoginResponse(
            token=token,
            user=UserOut(username=profile.username, name=profile.full_name, email=profile.email),
        ).model_dump()
    )
