"""Tests for Service Portfolio functionality."""

import pytest
import uuid
from datetime import datetime

from app.models.service_portfolio import (
    ServicePortfolio,
    RelationshipService,
    ServiceType,
    ServiceStatus,
)
from app.schemas.service_portfolio import (
    ServicePortfolioCreate,
    ServicePortfolioUpdate,
    ServicePortfolioResponse,
)


class TestServicePortfolioModel:
    """Tests for ServicePortfolio model."""

    def test_create_service_portfolio(self):
        """Test ServicePortfolio model creation with required fields."""
        sp = ServicePortfolio(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            name="Cloud Hosting Services",
            code="CHS",
            service_type="it_services",
            status="active",
        )
        assert sp.name == "Cloud Hosting Services"
        assert sp.code == "CHS"
        assert sp.service_type == "it_services"
        assert sp.status == "active"

    def test_service_portfolio_repr(self):
        """Test ServicePortfolio string representation."""
        sp = ServicePortfolio(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            name="Legal Advisory",
            code="LEGAL",
        )
        result = repr(sp)
        assert "LEGAL" in result
        assert "Legal Advisory" in result

    def test_default_status(self):
        """Test ServicePortfolio default status is 'active'."""
        sp = ServicePortfolio(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            name="Test Service",
            code="TST",
        )
        # Column default is 'active' but not applied outside DB session
        # Verify the column definition uses 'active' as default
        status_col = ServicePortfolio.__table__.columns["status"]
        assert status_col.default.arg == "active"


class TestRelationshipServiceModel:
    """Tests for RelationshipService model."""

    def test_create_relationship_service(self):
        """Test RelationshipService model creation."""
        rel_id = uuid.uuid4()
        sp_id = uuid.uuid4()
        rs = RelationshipService(
            id=uuid.uuid4(),
            relationship_id=rel_id,
            service_portfolio_id=sp_id,
            scope="Full managed IT support",
            is_active=True,
        )
        assert rs.relationship_id == rel_id
        assert rs.service_portfolio_id == sp_id
        assert rs.scope == "Full managed IT support"

    def test_default_is_active(self):
        """Test RelationshipService default is_active is True."""
        is_active_col = RelationshipService.__table__.columns["is_active"]
        assert is_active_col.default.arg is True


class TestServicePortfolioSchemas:
    """Tests for ServicePortfolio Pydantic schemas."""

    def test_create_schema(self):
        """Test ServicePortfolioCreate with required fields."""
        org_id = uuid.uuid4()
        data = ServicePortfolioCreate(
            name="Consulting Services",
            code="CONS",
            organization_id=org_id,
        )
        assert data.name == "Consulting Services"
        assert data.code == "CONS"
        assert data.organization_id == org_id
        assert data.service_type == ServiceType.OTHER
        assert data.status == ServiceStatus.ACTIVE

    def test_create_schema_with_all_fields(self):
        """Test ServicePortfolioCreate with all optional fields populated."""
        org_id = uuid.uuid4()
        data = ServicePortfolioCreate(
            name="Financial Advisory",
            code="FIN",
            description="Full-spectrum financial advisory services",
            service_type=ServiceType.FINANCIAL,
            status=ServiceStatus.PLANNED,
            organization_id=org_id,
        )
        assert data.description == "Full-spectrum financial advisory services"
        assert data.service_type == ServiceType.FINANCIAL
        assert data.status == ServiceStatus.PLANNED

    def test_update_schema_partial(self):
        """Test ServicePortfolioUpdate with partial data."""
        data = ServicePortfolioUpdate(name="Updated Name")
        assert data.name == "Updated Name"
        assert data.code is None
        assert data.service_type is None
        assert data.status is None
        assert data.description is None
        assert data.organization_id is None

    def test_response_schema(self):
        """Test ServicePortfolioResponse model_validate."""
        org_id = uuid.uuid4()
        sp_id = uuid.uuid4()
        now = datetime.utcnow()
        data = ServicePortfolioResponse.model_validate({
            "id": sp_id,
            "organization_id": org_id,
            "name": "Test Service",
            "code": "TST",
            "description": None,
            "service_type": ServiceType.IT_SERVICES,
            "status": ServiceStatus.ACTIVE,
            "created_at": now,
            "updated_at": now,
        })
        assert data.id == sp_id
        assert data.service_type == ServiceType.IT_SERVICES
        assert data.status == ServiceStatus.ACTIVE


class TestServiceTypeEnum:
    """Tests for ServiceType enum."""

    def test_all_service_types(self):
        """Test all expected service types exist."""
        expected = [
            "it_services", "consulting", "legal", "financial",
            "logistics", "manufacturing", "marketing", "hr",
            "procurement", "other",
        ]
        actual = [t.value for t in ServiceType]
        for stype in expected:
            assert stype in actual
        assert len(actual) == len(expected)


class TestServiceStatusEnum:
    """Tests for ServiceStatus enum."""

    def test_all_statuses(self):
        """Test all expected statuses exist."""
        expected = ["active", "inactive", "planned", "deprecated"]
        actual = [s.value for s in ServiceStatus]
        for status in expected:
            assert status in actual
        assert len(actual) == len(expected)
