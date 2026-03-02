"""Tests for Business Unit functionality."""

import pytest
import uuid
from datetime import datetime

from app.models.business_unit import BusinessUnit
from app.models.user import User, Role
from app.schemas.business_unit import (
    BusinessUnitCreate,
    BusinessUnitUpdate,
    BusinessUnitResponse,
)


class TestBusinessUnitModel:
    """Tests for BusinessUnit model."""

    def test_create_business_unit(self):
        """Test BusinessUnit model creation."""
        bu = BusinessUnit(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="Sales Department",
            code="SALES",
            description="Sales team",
            is_active=True,  # Explicitly set since not in DB session
        )
        assert bu.name == "Sales Department"
        assert bu.code == "SALES"
        assert bu.is_active is True

    def test_business_unit_full_path_no_parent(self):
        """Test full_path property without parent."""
        bu = BusinessUnit(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="Engineering",
            code="ENG",
        )
        bu.parent = None
        assert bu.full_path == "Engineering"

    def test_business_unit_repr(self):
        """Test BusinessUnit string representation."""
        bu = BusinessUnit(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="HR",
            code="HR",
        )
        assert "HR" in repr(bu)


class TestBusinessUnitSchemas:
    """Tests for BusinessUnit Pydantic schemas."""

    def test_create_schema_validation(self):
        """Test BusinessUnitCreate schema validation."""
        data = BusinessUnitCreate(
            name="Test BU",
            code="TEST",
            description="Test description",
        )
        assert data.name == "Test BU"
        assert data.code == "TEST"
        assert data.parent_id is None

    def test_create_schema_with_parent(self):
        """Test BusinessUnitCreate with parent_id."""
        parent_id = uuid.uuid4()
        data = BusinessUnitCreate(
            name="Child BU",
            code="CHILD",
            parent_id=parent_id,
        )
        assert data.parent_id == parent_id

    def test_update_schema_partial(self):
        """Test BusinessUnitUpdate with partial data."""
        data = BusinessUnitUpdate(name="Updated Name")
        assert data.name == "Updated Name"
        assert data.code is None
        assert data.is_active is None


class TestRoleEnum:
    """Tests for Role enum with BU_HEAD."""

    def test_bu_head_role_exists(self):
        """Test BU_HEAD role is defined."""
        assert Role.BU_HEAD.value == "bu_head"

    def test_all_roles(self):
        """Test all expected roles exist."""
        expected_roles = ["super_admin", "admin", "bu_head", "legal", "procurement", "viewer"]
        actual_roles = [r.value for r in Role]
        for role in expected_roles:
            assert role in actual_roles


class TestUserModelWithBU:
    """Tests for User model with business_unit_id."""

    def test_user_with_business_unit(self):
        """Test User model with business_unit_id."""
        bu_id = uuid.uuid4()
        user = User(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
            role=Role.LEGAL,
            business_unit_id=bu_id,
        )
        assert user.business_unit_id == bu_id

    def test_user_is_bu_head(self):
        """Test is_bu_head property."""
        user = User(
            id=uuid.uuid4(),
            username="buhead",
            email="buhead@example.com",
            password_hash="hashed",
            role=Role.BU_HEAD,
        )
        assert user.is_bu_head is True

    def test_user_not_bu_head(self):
        """Test is_bu_head property for non-BU_HEAD user."""
        user = User(
            id=uuid.uuid4(),
            username="legal",
            email="legal@example.com",
            password_hash="hashed",
            role=Role.LEGAL,
        )
        assert user.is_bu_head is False
