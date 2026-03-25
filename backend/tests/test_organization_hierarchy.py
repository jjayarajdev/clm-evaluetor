"""Tests for Organization Hierarchy functionality."""

import pytest
import uuid
from datetime import datetime

from app.models.organization import (
    Organization,
    OrganizationType,
    OrganizationSize,
    OrganizationLevel,
)
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationHierarchyResponse,
    OrganizationTreeNode,
)


class TestOrganizationHierarchy:
    """Tests for Organization model hierarchy fields."""

    def test_org_with_parent(self):
        """Test creating an Organization with parent_organization_id."""
        parent_id = uuid.uuid4()
        org = Organization(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="EMEA Division",
            code="EMEA",
            org_type="customer",
            parent_organization_id=parent_id,
            organization_level="division",
        )
        assert org.parent_organization_id == parent_id
        assert org.organization_level == "division"

    def test_org_with_level(self):
        """Test creating an Organization with organization_level='holding'."""
        org = Organization(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="Global Holdings Inc",
            code="GHI",
            org_type="customer",
            organization_level="holding",
        )
        assert org.organization_level == "holding"

    def test_org_without_parent(self):
        """Test that parent_organization_id is None by default."""
        org = Organization(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="Standalone Corp",
            code="STAND",
            org_type="vendor",
        )
        assert org.parent_organization_id is None


class TestOrganizationHierarchySchemas:
    """Tests for Organization hierarchy-related Pydantic schemas."""

    def test_create_with_parent(self):
        """Test OrganizationCreate with parent_organization_id."""
        parent_id = uuid.uuid4()
        data = OrganizationCreate(
            name="North America Ops",
            code="NA-OPS",
            org_type=OrganizationType.INTERNAL,
            parent_organization_id=parent_id,
        )
        assert data.parent_organization_id == parent_id
        assert data.organization_level is None

    def test_create_with_level(self):
        """Test OrganizationCreate with organization_level."""
        data = OrganizationCreate(
            name="Subsidiary Ltd",
            code="SUB",
            org_type=OrganizationType.CUSTOMER,
            organization_level=OrganizationLevel.SUBSIDIARY,
        )
        assert data.organization_level == OrganizationLevel.SUBSIDIARY
        assert data.parent_organization_id is None

    def test_hierarchy_response(self):
        """Test OrganizationHierarchyResponse schema validation."""
        now = datetime.utcnow()
        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()

        parent_data = {
            "id": parent_id,
            "name": "Parent Corp",
            "code": "PARENT",
            "org_type": OrganizationType.CUSTOMER,
            "parent_organization_id": None,
            "organization_level": OrganizationLevel.HOLDING,
            "relationship_owner_id": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        child_data = {
            "id": child_id,
            "name": "Child Division",
            "code": "CHILD",
            "org_type": OrganizationType.CUSTOMER,
            "parent_organization_id": parent_id,
            "organization_level": OrganizationLevel.DIVISION,
            "relationship_owner_id": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        hierarchy = OrganizationHierarchyResponse(
            organization=OrganizationResponse.model_validate(child_data),
            parent=OrganizationResponse.model_validate(parent_data),
            parent_chain=[OrganizationResponse.model_validate(parent_data)],
            children=[],
        )
        assert hierarchy.organization.id == child_id
        assert hierarchy.parent.id == parent_id
        assert len(hierarchy.parent_chain) == 1
        assert hierarchy.parent_chain[0].organization_level == OrganizationLevel.HOLDING
        assert hierarchy.children == []

    def test_tree_node(self):
        """Test OrganizationTreeNode schema validation."""
        node_id = uuid.uuid4()
        child_id = uuid.uuid4()
        node = OrganizationTreeNode.model_validate({
            "id": node_id,
            "name": "Root Org",
            "code": "ROOT",
            "org_type": OrganizationType.CUSTOMER,
            "organization_level": OrganizationLevel.HOLDING,
            "is_active": True,
            "children": [
                {
                    "id": child_id,
                    "name": "Sub Org",
                    "code": "SUB",
                    "org_type": OrganizationType.CUSTOMER,
                    "organization_level": OrganizationLevel.SUBSIDIARY,
                    "is_active": True,
                    "children": [],
                }
            ],
        })
        assert node.id == node_id
        assert node.organization_level == OrganizationLevel.HOLDING
        assert len(node.children) == 1
        assert node.children[0].id == child_id
        assert node.children[0].name == "Sub Org"
        assert node.children[0].organization_level == OrganizationLevel.SUBSIDIARY

    def test_tree_node_no_children(self):
        """Test OrganizationTreeNode with no children (leaf node)."""
        node = OrganizationTreeNode.model_validate({
            "id": uuid.uuid4(),
            "name": "Leaf Dept",
            "code": "LEAF",
            "org_type": OrganizationType.INTERNAL,
            "organization_level": OrganizationLevel.DEPARTMENT,
            "is_active": True,
        })
        assert node.children == []
        assert node.organization_level == OrganizationLevel.DEPARTMENT
