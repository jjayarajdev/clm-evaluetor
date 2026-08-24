"""Pydantic schemas for authentication."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from app.core.security import BCRYPT_MAX_PASSWORD_BYTES


def _enforce_bcrypt_byte_limit(v: str) -> str:
    if len(v.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes"
        )
    return v


# For fields that SET a password (hash_password rejects >72 bytes — validate
# here so the client gets a 422 instead of a 500). Login fields stay uncapped:
# a pre-existing longer password still verifies via bcrypt's truncation.
NewPassword = Annotated[
    str, Field(min_length=8), AfterValidator(_enforce_bcrypt_byte_limit)
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
