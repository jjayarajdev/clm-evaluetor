"""Tests for authentication and security functions."""

import pytest
from app.core.security import hash_password, create_access_token, verify_password
from app.config import settings


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_password_hash_is_different_from_plain(self):
        """Test that hashed password is different from plain text."""
        password = "my_secret_password"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > len(password)

    def test_same_password_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        password = "my_secret_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Should be different due to salt

    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "my_secret_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Test verifying incorrect password."""
        password = "my_secret_password"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False

    def test_empty_password_hashes(self):
        """Test that empty password can be hashed."""
        hashed = hash_password("")
        assert hashed is not None
        assert len(hashed) > 0

    def test_long_password_hashes(self):
        """Test that passwords up to bcrypt limit can be hashed."""
        # bcrypt has a 72-byte limit
        password = "a" * 72
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_special_characters_in_password(self):
        """Test passwords with special characters."""
        password = "P@ssw0rd!#$%^&*()_+-=[]{}|;':\",./<>?"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_unicode_password(self):
        """Test passwords with unicode characters."""
        password = "密码123🔐"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token(self):
        """Test access token creation."""
        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="admin",
            tenant_id="tenant-123",
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_contains_claims(self):
        """Test access token contains expected claims."""
        from jose import jwt

        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="admin",
            tenant_id="tenant-123",
        )

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        assert payload["sub"] == "user-123"
        assert payload["username"] == "testuser"
        assert payload["role"] == "admin"
        assert payload["tenant_id"] == "tenant-123"
        assert "exp" in payload

    def test_token_without_tenant(self):
        """Test token creation without tenant_id (super admin)."""
        from jose import jwt

        token = create_access_token(
            user_id="admin-123",
            username="superadmin",
            role="super_admin",
            tenant_id=None,
        )

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        assert payload["sub"] == "admin-123"
        assert payload["tenant_id"] is None

    def test_token_expiration(self):
        """Test that token has expiration time."""
        from jose import jwt
        from datetime import datetime

        token = create_access_token(
            user_id="user-123",
            username="testuser",
            role="admin",
            tenant_id="tenant-123",
        )

        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        exp_time = datetime.fromtimestamp(payload["exp"])
        assert exp_time > datetime.utcnow()


class TestRoles:
    """Tests for role definitions."""

    def test_role_enum_values(self):
        """Test that role enum has expected values."""
        from app.models.user import Role

        assert Role.SUPER_ADMIN.value == "super_admin"
        assert Role.ADMIN.value == "admin"
        assert Role.LEGAL.value == "legal"
        assert Role.PROCUREMENT.value == "procurement"
        assert Role.VIEWER.value == "viewer"

    def test_role_comparison(self):
        """Test role comparison."""
        from app.models.user import Role

        assert Role.SUPER_ADMIN == Role.SUPER_ADMIN
        assert Role.ADMIN != Role.LEGAL


class TestUserModel:
    """Tests for User model."""

    def test_user_creation(self):
        """Test creating a user model."""
        from app.models.user import User, Role
        import uuid
        from datetime import datetime

        user = User(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            password_hash=hash_password("password123"),
            role=Role.ADMIN,
            is_active=True,
            created_at=datetime.utcnow(),
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == Role.ADMIN
        assert user.is_active is True

    def test_user_password_not_stored_plain(self):
        """Test that password is not stored in plain text."""
        from app.models.user import User, Role
        import uuid
        from datetime import datetime

        password = "my_secret"
        user = User(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            password_hash=hash_password(password),
            role=Role.ADMIN,
            is_active=True,
            created_at=datetime.utcnow(),
        )

        assert user.password_hash != password
        assert verify_password(password, user.password_hash) is True


class TestTenantModel:
    """Tests for Tenant model."""

    def test_tenant_creation(self):
        """Test creating a tenant model."""
        from app.models.tenant import Tenant
        import uuid
        from datetime import datetime

        tenant = Tenant(
            id=uuid.uuid4(),
            name="Acme Corp",
            slug="acme-corp",
            is_active=True,
            created_at=datetime.utcnow(),
        )

        assert tenant.name == "Acme Corp"
        assert tenant.slug == "acme-corp"
        assert tenant.is_active is True

    def test_tenant_slug_format(self):
        """Test tenant slug follows expected format."""
        from app.models.tenant import Tenant
        import uuid
        from datetime import datetime

        tenant = Tenant(
            id=uuid.uuid4(),
            name="Test Company",
            slug="test-company",
            is_active=True,
            created_at=datetime.utcnow(),
        )

        # Slug should be lowercase with hyphens
        assert tenant.slug == tenant.slug.lower()
        assert " " not in tenant.slug
