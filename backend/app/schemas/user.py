"""Pydantic schemas for user management."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import Role


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[^\s]+$')
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Role = Role.LEGAL
    tenant_id: str | None = None  # Super admin can specify target tenant


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    username: str | None = Field(None, min_length=3, max_length=50, pattern=r'^[^\s]+$')
    email: EmailStr | None = None
    role: Role | None = None
    is_active: bool | None = None


class UserPasswordUpdate(BaseModel):
    """Schema for updating user password (admin)."""

    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """Schema for user response."""

    id: str
    username: str
    email: str
    role: str
    is_active: bool
    tenant_id: str | None = None
    tenant_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Schema for paginated user list."""

    users: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserFilter(BaseModel):
    """Schema for filtering users."""

    role: Role | None = None
    is_active: bool | None = None
    search: str | None = None  # Search in username or email
