"""Tests for Organization Officer functionality."""

import pytest
import uuid
from datetime import datetime

from app.models.organization_officer import (
    OrganizationOfficer,
    GovernanceRole,
    OfficerSide,
)
from app.models.organization import OrganizationLevel
from app.schemas.organization_officer import (
    OfficerCreate,
    OfficerUpdate,
    OfficerResponse,
)


class TestOrganizationOfficerModel:
    """Tests for OrganizationOfficer model."""

    def test_create_officer(self):
        """Test OrganizationOfficer model creation with all fields."""
        org_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        officer = OrganizationOfficer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            organization_id=org_id,
            name="Jane Smith",
            title="VP of Engineering",
            email="jane.smith@example.com",
            phone="+1-555-0100",
            department="Engineering",
            governance_role="account_manager",
            side="internal",
            is_primary=True,
            is_active=True,
            notes="Key technical contact",
        )
        assert officer.name == "Jane Smith"
        assert officer.title == "VP of Engineering"
        assert officer.email == "jane.smith@example.com"
        assert officer.phone == "+1-555-0100"
        assert officer.department == "Engineering"
        assert officer.governance_role == "account_manager"
        assert officer.side == "internal"
        assert officer.is_primary is True
        assert officer.is_active is True
        assert officer.notes == "Key technical contact"
        assert officer.organization_id == org_id

    def test_officer_repr(self):
        """Test OrganizationOfficer string representation."""
        officer = OrganizationOfficer(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            name="John Doe",
            governance_role="executive_sponsor",
        )
        result = repr(officer)
        assert "John Doe" in result
        assert "executive_sponsor" in result

    def test_default_is_primary(self):
        """Test OrganizationOfficer default is_primary is False."""
        is_primary_col = OrganizationOfficer.__table__.columns["is_primary"]
        assert is_primary_col.default.arg is False

    def test_default_is_active(self):
        """Test OrganizationOfficer default is_active is True."""
        is_active_col = OrganizationOfficer.__table__.columns["is_active"]
        assert is_active_col.default.arg is True


class TestOfficerSchemas:
    """Tests for Officer Pydantic schemas."""

    def test_create_schema(self):
        """Test OfficerCreate schema validation."""
        data = OfficerCreate(
            name="Alice Johnson",
            title="Account Manager",
            email="alice@example.com",
            governance_role=GovernanceRole.ACCOUNT_MANAGER,
            side=OfficerSide.INTERNAL,
        )
        assert data.name == "Alice Johnson"
        assert data.title == "Account Manager"
        assert data.email == "alice@example.com"
        assert data.governance_role == GovernanceRole.ACCOUNT_MANAGER
        assert data.side == OfficerSide.INTERNAL
        assert data.is_primary is False
        assert data.phone is None
        assert data.department is None
        assert data.notes is None

    def test_update_schema_partial(self):
        """Test OfficerUpdate with partial data."""
        data = OfficerUpdate(name="Updated Name", is_active=False)
        assert data.name == "Updated Name"
        assert data.is_active is False
        assert data.title is None
        assert data.email is None
        assert data.governance_role is None
        assert data.side is None
        assert data.is_primary is None
        assert data.phone is None
        assert data.department is None
        assert data.notes is None

    def test_response_schema(self):
        """Test OfficerResponse model_validate."""
        officer_id = uuid.uuid4()
        org_id = uuid.uuid4()
        now = datetime.utcnow()
        data = OfficerResponse.model_validate({
            "id": officer_id,
            "organization_id": org_id,
            "name": "Bob Williams",
            "title": "CTO",
            "email": "bob@example.com",
            "phone": None,
            "department": "Technology",
            "governance_role": GovernanceRole.TECHNICAL_LEAD,
            "side": OfficerSide.INTERNAL,
            "is_primary": True,
            "is_active": True,
            "notes": None,
            "created_at": now,
            "updated_at": now,
        })
        assert data.id == officer_id
        assert data.name == "Bob Williams"
        assert data.governance_role == GovernanceRole.TECHNICAL_LEAD
        assert data.is_primary is True


class TestGovernanceRoleEnum:
    """Tests for GovernanceRole enum."""

    def test_all_roles(self):
        """Test all expected governance roles exist."""
        expected = [
            "account_manager",
            "service_delivery_manager",
            "relationship_owner",
            "executive_sponsor",
            "commercial_manager",
            "technical_lead",
            "operations_lead",
            "compliance_officer",
            "other",
        ]
        actual = [r.value for r in GovernanceRole]
        for role in expected:
            assert role in actual
        assert len(actual) == len(expected)


class TestOfficerSideEnum:
    """Tests for OfficerSide enum."""

    def test_internal_external(self):
        """Test both officer side values exist."""
        assert OfficerSide.INTERNAL.value == "internal"
        assert OfficerSide.EXTERNAL.value == "external"
        assert len(OfficerSide) == 2


class TestOrganizationLevel:
    """Tests for OrganizationLevel enum."""

    def test_all_levels(self):
        """Test all expected organization levels exist."""
        expected = ["holding", "subsidiary", "division", "branch", "department"]
        actual = [level.value for level in OrganizationLevel]
        for level in expected:
            assert level in actual
        assert len(actual) == len(expected)
