"""Security utilities for password hashing and JWT tokens."""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings


class TokenData(BaseModel):
    """Data encoded in JWT token."""

    user_id: str
    username: str
    role: str
    tenant_id: str | None  # None for super_admin
    business_unit_id: str | None = None
    exp: datetime


class TokenPayload(BaseModel):
    """Decoded token payload."""

    sub: str  # user_id
    username: str
    role: str
    tenant_id: str | None = None  # None for super_admin
    business_unit_id: str | None = None
    exp: int


# =============================================================================
# Password Hashing
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password.

    Returns:
        Hashed password string.
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify.
        hashed_password: Hashed password to compare against.

    Returns:
        True if password matches, False otherwise.
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# =============================================================================
# JWT Token Management
# =============================================================================


def create_access_token(
    user_id: str,
    username: str,
    role: str,
    tenant_id: str | None = None,
    business_unit_id: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: User's unique identifier.
        username: User's username.
        role: User's role (super_admin, admin, legal, procurement, viewer).
        tenant_id: User's tenant ID (None for super_admin).
        business_unit_id: User's business unit ID (None if not assigned).
        expires_delta: Optional custom expiration time.

    Returns:
        Encoded JWT token string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            hours=settings.jwt_expiration_hours
        )

    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "tenant_id": tenant_id,
        "business_unit_id": business_unit_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string.

    Returns:
        TokenPayload if valid, None if invalid or expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(
            sub=payload["sub"],
            username=payload["username"],
            role=payload["role"],
            tenant_id=payload.get("tenant_id"),
            business_unit_id=payload.get("business_unit_id"),
            exp=payload["exp"],
        )
    except JWTError:
        return None


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return its payload.

    Args:
        token: JWT token string.

    Returns:
        Token payload dict if valid, None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


def is_token_expired(token: str) -> bool:
    """Check if a token is expired.

    Args:
        token: JWT token string.

    Returns:
        True if expired or invalid, False if still valid.
    """
    payload = decode_token(token)
    if payload is None:
        return True

    exp_datetime = datetime.fromtimestamp(payload.exp, tz=timezone.utc)
    return datetime.now(timezone.utc) > exp_datetime
