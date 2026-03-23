"""
Authentication adapter for Beacon-Safe.

This backend uses a mock JWT scheme suitable for demos:
- /auth/login accepts any username/password
- issues a token that encodes the username (NOT secure)
- protected endpoints require Authorization: Bearer <token>

Contract:
- Token format: "mock-jwt:<username>"
- Parsing validates the prefix and non-empty username.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    """Authenticated request context extracted from the Authorization header."""

    username: str
    token: str


# PUBLIC_INTERFACE
def issue_mock_token(username: str) -> str:
    """
    Issue a mock token.

    Inputs:
    - username: non-empty

    Output:
    - token string, stable format for parsing later
    """
    safe_username = (username or "").strip()
    if not safe_username:
        raise ValueError("username must be non-empty")
    return f"mock-jwt:{safe_username}"


def parse_mock_token(token: str) -> str:
    """Parse token and return username or raise ValueError."""
    if not token:
        raise ValueError("Missing token")

    if not token.startswith("mock-jwt:"):
        raise ValueError("Invalid token format")

    username = token[len("mock-jwt:") :].strip()
    if not username:
        raise ValueError("Invalid token: missing username")
    return username


# PUBLIC_INTERFACE
async def require_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthContext:
    """
    FastAPI dependency enforcing Bearer auth.

    Errors:
    - 401 if missing/invalid token
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    try:
        username = parse_mock_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return AuthContext(username=username, token=credentials.credentials)
