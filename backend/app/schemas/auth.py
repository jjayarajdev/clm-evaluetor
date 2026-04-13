"""Pydantic schemas for authentication."""

from pydantic import BaseModel, EmailStr, Field


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
    tenant_id: str | None = None
    tenant_name: str | None = None
    business_unit_id: str | None = None
    business_unit_name: str | None = None


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Request schema for password change."""

    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


# Update forward references
TokenResponse.model_rebuild()
