"""Tests for External User and Contract Sharing functionality."""

import pytest
import uuid
from datetime import datetime, timedelta

from app.models.external_user import ExternalUser
from app.models.contract_share import ContractShare
from app.models.contract_comment import ContractComment
from app.models.external_access import ExternalAccessToken, TokenType
from app.schemas.external_user import (
    ExternalUserCreate,
    ExternalUserInvite,
    ExternalUserResponse,
)
from app.schemas.contract_share import (
    ContractShareCreate,
    ContractShareResponse,
)
from app.schemas.contract_comment import (
    ContractCommentCreate,
    ContractCommentResponse,
)


class TestExternalUserModel:
    """Tests for ExternalUser model."""

    def test_create_external_user(self):
        """Test ExternalUser model creation."""
        ext_user = ExternalUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="vendor@example.com",
            full_name="John Vendor",
            company_name="Vendor Corp",
            is_active=True,  # Explicitly set since not in DB session
            access_count=0,  # Explicitly set since not in DB session
        )
        assert ext_user.email == "vendor@example.com"
        assert ext_user.full_name == "John Vendor"
        assert ext_user.is_active is True
        assert ext_user.access_count == 0

    def test_external_user_display_name_with_full_name(self):
        """Test display_name property with full_name."""
        ext_user = ExternalUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="vendor@example.com",
            full_name="John Vendor",
        )
        assert ext_user.display_name == "John Vendor"

    def test_external_user_display_name_without_full_name(self):
        """Test display_name property without full_name."""
        ext_user = ExternalUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="vendor@example.com",
        )
        assert ext_user.display_name == "vendor"

    def test_record_access(self):
        """Test record_access method."""
        ext_user = ExternalUser(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="vendor@example.com",
            access_count=0,  # Explicitly set since not in DB session
        )
        assert ext_user.access_count == 0
        assert ext_user.last_access_at is None

        ext_user.record_access()

        assert ext_user.access_count == 1
        assert ext_user.last_access_at is not None


class TestContractShareModel:
    """Tests for ContractShare model."""

    def test_create_contract_share(self):
        """Test ContractShare model creation."""
        share = ContractShare(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            external_user_id=uuid.uuid4(),
            shared_by_id=uuid.uuid4(),
            can_download=True,
            can_comment=True,
            is_revoked=False,  # Explicitly set since not in DB session
            access_count=0,  # Explicitly set since not in DB session
        )
        assert share.can_download is True
        assert share.can_comment is True
        assert share.is_revoked is False
        assert share.access_count == 0

    def test_share_is_active_without_expiration(self):
        """Test is_active property without expiration."""
        share = ContractShare(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            external_user_id=uuid.uuid4(),
            shared_by_id=uuid.uuid4(),
        )
        assert share.is_active is True

    def test_share_is_active_revoked(self):
        """Test is_active property when revoked."""
        share = ContractShare(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            external_user_id=uuid.uuid4(),
            shared_by_id=uuid.uuid4(),
            is_revoked=True,
        )
        assert share.is_active is False

    def test_share_is_active_expired(self):
        """Test is_active property when expired."""
        share = ContractShare(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            external_user_id=uuid.uuid4(),
            shared_by_id=uuid.uuid4(),
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert share.is_active is False

    def test_revoke_share(self):
        """Test revoke method."""
        share = ContractShare(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            external_user_id=uuid.uuid4(),
            shared_by_id=uuid.uuid4(),
        )
        revoked_by = uuid.uuid4()
        share.revoke(revoked_by)

        assert share.is_revoked is True
        assert share.revoked_at is not None
        assert share.revoked_by_id == revoked_by


class TestContractCommentModel:
    """Tests for ContractComment model."""

    def test_create_internal_comment(self):
        """Test ContractComment with internal user."""
        comment = ContractComment(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content="This is an internal comment",
            is_internal=True,
        )
        assert comment.user_id is not None
        assert comment.external_user_id is None
        assert comment.is_internal is True
        assert comment.is_internal_author is True

    def test_create_external_comment(self):
        """Test ContractComment with external user."""
        comment = ContractComment(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            external_user_id=uuid.uuid4(),
            content="This is an external comment",
            is_internal=False,
        )
        assert comment.user_id is None
        assert comment.external_user_id is not None
        assert comment.is_internal is False
        assert comment.is_internal_author is False

    def test_resolve_comment(self):
        """Test resolve method."""
        comment = ContractComment(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content="Needs resolution",
        )
        resolved_by = uuid.uuid4()
        comment.resolve(resolved_by)

        assert comment.is_resolved is True
        assert comment.resolved_at is not None
        assert comment.resolved_by_id == resolved_by

    def test_soft_delete(self):
        """Test soft_delete method."""
        comment = ContractComment(
            id=uuid.uuid4(),
            contract_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content="To be deleted",
        )
        comment.soft_delete()

        assert comment.is_deleted is True
        assert comment.deleted_at is not None


class TestExternalAccessTokenModel:
    """Tests for ExternalAccessToken model with contract access."""

    def test_contract_access_token_type(self):
        """Test CONTRACT_ACCESS token type exists."""
        assert TokenType.CONTRACT_ACCESS.value == "contract_access"

    def test_create_contract_access_token(self):
        """Test creating a contract access token."""
        ext_user_id = uuid.uuid4()
        contract_id = uuid.uuid4()
        token = ExternalAccessToken(
            id=uuid.uuid4(),
            token=ExternalAccessToken.generate_token(),
            token_type=TokenType.CONTRACT_ACCESS,
            external_user_id=ext_user_id,
            contract_id=contract_id,
            recipient_email="vendor@example.com",
            expires_at=datetime.utcnow() + timedelta(days=30),
            is_revoked=False,
            use_count=0,
        )
        assert token.token_type == TokenType.CONTRACT_ACCESS
        assert token.external_user_id == ext_user_id
        assert token.contract_id == contract_id
        assert len(token.token) > 20  # Secure token length

    def test_token_is_valid(self):
        """Test is_valid property."""
        token = ExternalAccessToken.create_token(
            token_type=TokenType.CONTRACT_ACCESS,
            expires_in_days=30,
        )
        assert token.is_valid is True

    def test_token_expired(self):
        """Test is_valid for expired token."""
        token = ExternalAccessToken(
            id=uuid.uuid4(),
            token="test_token",
            token_type=TokenType.CONTRACT_ACCESS,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert token.is_valid is False

    def test_token_revoked(self):
        """Test is_valid for revoked token."""
        token = ExternalAccessToken(
            id=uuid.uuid4(),
            token="test_token",
            token_type=TokenType.CONTRACT_ACCESS,
            expires_at=datetime.utcnow() + timedelta(days=30),
            is_revoked=True,
        )
        assert token.is_valid is False


class TestExternalUserSchemas:
    """Tests for External User Pydantic schemas."""

    def test_create_schema_validation(self):
        """Test ExternalUserCreate schema validation."""
        data = ExternalUserCreate(
            email="vendor@example.com",
            full_name="John Vendor",
            company_name="Vendor Corp",
        )
        assert data.email == "vendor@example.com"
        assert data.full_name == "John Vendor"

    def test_invite_schema_with_contracts(self):
        """Test ExternalUserInvite schema with contract IDs."""
        contract_ids = [uuid.uuid4(), uuid.uuid4()]
        data = ExternalUserInvite(
            email="vendor@example.com",
            contract_ids=contract_ids,
            can_download=True,
            can_comment=True,
            expires_in_days=30,
        )
        assert len(data.contract_ids) == 2
        assert data.can_download is True
        assert data.expires_in_days == 30


class TestContractShareSchemas:
    """Tests for Contract Share Pydantic schemas."""

    def test_create_schema_validation(self):
        """Test ContractShareCreate schema validation."""
        data = ContractShareCreate(
            external_user_id=uuid.uuid4(),
            can_download=True,
            can_comment=True,
            expires_in_days=30,
        )
        assert data.can_download is True
        assert data.can_comment is True
        assert data.expires_in_days == 30


class TestContractCommentSchemas:
    """Tests for Contract Comment Pydantic schemas."""

    def test_create_schema_validation(self):
        """Test ContractCommentCreate schema validation."""
        data = ContractCommentCreate(
            content="This is a test comment",
            is_internal=False,
        )
        assert data.content == "This is a test comment"
        assert data.is_internal is False
        assert data.parent_id is None

    def test_create_schema_with_clause_reference(self):
        """Test ContractCommentCreate with clause reference."""
        clause_id = uuid.uuid4()
        data = ContractCommentCreate(
            content="Comment on specific clause",
            clause_id=clause_id,
            section_reference="Section 5.2",
        )
        assert data.clause_id == clause_id
        assert data.section_reference == "Section 5.2"
