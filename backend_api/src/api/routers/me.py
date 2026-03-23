from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.api.core.auth import AuthContext, require_auth_context
from src.api.schemas import PreferencesOut, ProfileResponse, UpdateSettingsRequest, UserOut
from src.api.services.user_service import get_profile_by_username, update_settings

router = APIRouter(tags=["Account"])


@router.get(
    "/me",
    response_model=ProfileResponse,
    summary="Get current user profile and preferences",
    operation_id="me_get",
)
# PUBLIC_INTERFACE
async def get_me(request: Request, auth: AuthContext = Depends(require_auth_context)) -> JSONResponse:
    """
    Get profile details + preferences for the authenticated user.

    Auth:
    - Requires Authorization: Bearer <token>

    Returns:
    - ProfileResponse { user, preferences }
    """
    pool = request.app.state.db_pool
    profile = await get_profile_by_username(pool, auth.username)

    return JSONResponse(
        ProfileResponse(
            user=UserOut(username=profile.username, name=profile.full_name, email=profile.email),
            preferences=PreferencesOut(theme=profile.theme),  # type: ignore[arg-type]
        ).model_dump()
    )


@router.patch(
    "/settings",
    response_model=ProfileResponse,
    summary="Update profile and/or preferences (persisted)",
    operation_id="settings_update",
)
# PUBLIC_INTERFACE
async def patch_settings(
    payload: UpdateSettingsRequest,
    request: Request,
    auth: AuthContext = Depends(require_auth_context),
) -> JSONResponse:
    """
    Update settings for the authenticated user.

    Supported updates:
    - payload.name -> users.full_name
    - payload.email -> users.email
    - payload.theme -> user_preferences.theme

    Auth:
    - Requires Authorization: Bearer <token>

    Returns:
    - Updated ProfileResponse { user, preferences }
    """
    pool = request.app.state.db_pool
    updated = await update_settings(
        pool,
        auth.username,
        name=payload.name,
        email=payload.email,
        theme=payload.theme,
    )

    return JSONResponse(
        ProfileResponse(
            user=UserOut(username=updated.username, name=updated.full_name, email=updated.email),
            preferences=PreferencesOut(theme=updated.theme),  # type: ignore[arg-type]
        ).model_dump()
    )
