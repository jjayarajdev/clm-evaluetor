"""Pydantic schemas for authentication."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES


# Policy for NEW passwords only. Login/current-password fields are exempt so
# every pre-existing credential keeps working; the policy applies as passwords
# are set or changed.
MIN_PASSWORD_LENGTH = 12


def _enforce_password_policy(v: str) -> str:
    if len(v.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes"
        )
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain a lowercase letter")
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain an uppercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain a digit")
    return v


# For fields that SET a password: length + character-class policy, plus the
# bcrypt byte cap (hash_password rejects >72 bytes — validate here so the
# client gets a 422 instead of a 500).
NewPassword = Annotated[
    str,
    Field(min_length=MIN_PASSWORD_LENGTH),
    AfterValidator(_enforce_password_policy),
]


class LoginRequest(BaseModel):
    """Request schema for login endpoint."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """Response schema for successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until expiration
    user: "UserInfo"


class UserInfo(BaseModel):
    """Basic user information returned with token."""

    id: str
    username: str
    email: str
    full_name: str | None = None
    role: str
    preferred_language: str = "en"
    tenant_id: str | None = None
    tenant_name: str | None = None
    business_unit_id: str | None = None
    business_unit_name: str | None = None
    # Effective permissions from the DB role-permission matrix — drives the
    # frontend (permissionsForUser prefers this over its static fallback map).
    permissions: list[str] = []


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Request schema for password change."""

    current_password: str = Field(..., min_length=8)
    new_password: NewPassword


# Update forward references
TokenResponse.model_rebuild()
