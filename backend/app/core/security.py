"""Security utilities for password hashing and JWT tokens."""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError

from app.config import settings

# Tokens minted by create_access_token carry this type. Decoding rejects any
# other type so a token issued for a different purpose (e.g. a future refresh or
# password-reset token signed with the same secret) can never be presented as an
# access token.
ACCESS_TOKEN_TYPE = "access"

# Clock-skew tolerance (seconds) applied to exp/iat validation so minor drift
# between hosts doesn't spuriously reject a valid token at the boundary.
_LEEWAY_SECONDS = 10

# python-jose validation options: reject a token missing exp or sub outright
# (raising JWTError rather than KeyError→500 downstream).
_DECODE_OPTIONS = {"require_exp": True, "require_sub": True, "leeway": _LEEWAY_SECONDS}


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


def _decode_and_verify(token: str) -> dict[str, Any] | None:
    """Decode a JWT, pinning the algorithm and enforcing required claims + type.

    Returns the raw payload dict, or None for any invalid/expired/wrong-type
    token. Signature is verified against a single pinned algorithm (no alg=none
    or HS/RS confusion), exp/sub are required, and the token ``type`` must be an
    access token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options=_DECODE_OPTIONS,
        )
    except JWTError:
        return None
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        return None
    return payload


def decode_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string.

    Returns:
        TokenPayload if valid, None if invalid, expired, or the wrong type.
    """
    payload = _decode_and_verify(token)
    if payload is None:
        return None
    try:
        return TokenPayload(
            sub=payload["sub"],
            username=payload["username"],
            role=payload["role"],
            tenant_id=payload.get("tenant_id"),
            business_unit_id=payload.get("business_unit_id"),
            exp=payload["exp"],
        )
    except (KeyError, ValidationError):
        # A signature-valid token missing non-required claims (username/role) is
        # still unusable — treat as invalid rather than 500.
        return None


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return its raw payload.

    Args:
        token: JWT token string.

    Returns:
        Token payload dict if valid, None if invalid.
    """
    return _decode_and_verify(token)


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
