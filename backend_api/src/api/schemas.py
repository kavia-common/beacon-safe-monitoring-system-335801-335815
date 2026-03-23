"""
Pydantic schemas for the Beacon-Safe API.

Notes:
- Frontend expects:
  - POST /auth/login -> { token, user }
  - GET /devices -> Device[]
  - GET /me -> { user } (we also include preferences as additive fields)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    """User payload returned to the frontend."""

    username: str = Field(..., description="Unique username.")
    name: Optional[str] = Field(None, description="Display name (full name).")
    email: Optional[str] = Field(None, description="Email address.")


class LoginRequest(BaseModel):
    """Login request body (accepts any credentials in this mock implementation)."""

    username: str = Field(..., min_length=1, description="Username to log in with.")
    password: str = Field(..., min_length=1, description="Password (ignored for mock auth).")


class LoginResponse(BaseModel):
    """Login response containing a mock token and user object."""

    token: str = Field(..., description="Mock JWT to use as Bearer token.")
    user: UserOut = Field(..., description="Authenticated user object.")


DeviceStatus = Literal["online", "offline", "warning"]


class DeviceOut(BaseModel):
    """Device card payload."""

    id: str = Field(..., description="Device ID.")
    name: str = Field(..., description="Device name.")
    location: str = Field(..., description="Human-readable location label.")
    status: DeviceStatus = Field(..., description="Device status indicator.")
    batteryLevel: int = Field(..., ge=0, le=100, description="Battery percentage (0..100).")


ThemeMode = Literal["dark", "light"]


class PreferencesOut(BaseModel):
    """User preference payload."""

    theme: ThemeMode = Field(..., description="UI theme preference.")


class ProfileResponse(BaseModel):
    """Profile response for /me."""

    user: UserOut = Field(..., description="User profile.")
    preferences: PreferencesOut = Field(..., description="User preferences.")


class UpdateSettingsRequest(BaseModel):
    """
    Settings update payload.

    Supports updating:
    - profile: name/email
    - preferences: theme
    """

    name: Optional[str] = Field(None, description="New display name.")
    email: Optional[str] = Field(None, description="New email address.")
    theme: Optional[ThemeMode] = Field(None, description="Theme preference (light/dark).")
