"""External access token model for stakeholder portal (Evaluetor features)."""

import enum
import uuid
import secrets
from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, String, Text, Enum, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class TokenType(str, enum.Enum):
    """Type of external access token."""
    PERCEPTION_SCORING = "perception_scoring"
    SURVEY_RESPONSE = "survey_response"
    DOCUMENT_VIEW = "document_view"
    MULTI_PURPOSE = "multi_purpose"
    CONTRACT_ACCESS = "contract_access"


class ExternalAccessToken(Base):
    """Token for external stakeholder access to limited portal features.

    Enables clients/vendors to submit perception scores or survey
    responses without requiring a full user account.
    """

    __tablename__ = "external_access_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Token itself
    token = Column(String(100), nullable=False, unique=True, index=True)
    token_type = Column(Enum(TokenType), nullable=False)

    # Scope
    relationship_id = Column(UUID(as_uuid=True), ForeignKey("business_relationships.id"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    survey_instance_id = Column(UUID(as_uuid=True), ForeignKey("survey_instances.id"), nullable=True)
    external_user_id = Column(UUID(as_uuid=True), ForeignKey("external_users.id"), nullable=True, index=True)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=True, index=True)

    # Recipient
    recipient_email = Column(String(255), nullable=True)
    recipient_name = Column(String(255), nullable=True)

    # Validity
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(Text, nullable=True)

    # Usage tracking
    max_uses = Column(Integer, nullable=True, default=1)  # None = unlimited
    use_count = Column(Integer, default=0, nullable=False)
    first_used_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)

    # Creator
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    relationship = sa_relationship("BusinessRelationship")
    organization = sa_relationship("Organization")
    survey_instance = sa_relationship("SurveyInstance")
    created_by = sa_relationship("User", foreign_keys=[created_by_id])
    external_user = sa_relationship("ExternalUser", back_populates="access_tokens")
    contract = sa_relationship("Contract")

    def __repr__(self) -> str:
        return f"<ExternalAccessToken {self.token[:8]}... ({self.token_type.value})>"

    @classmethod
    def generate_token(cls) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    @classmethod
    def create_token(
        cls,
        token_type: TokenType,
        expires_in_days: int = 30,
        relationship_id: uuid.UUID = None,
        organization_id: uuid.UUID = None,
        survey_instance_id: uuid.UUID = None,
        recipient_email: str = None,
        recipient_name: str = None,
        max_uses: int = None,
        created_by_id: uuid.UUID = None,
    ) -> "ExternalAccessToken":
        """Factory method to create a new access token."""
        return cls(
            token=cls.generate_token(),
            token_type=token_type,
            relationship_id=relationship_id,
            organization_id=organization_id,
            survey_instance_id=survey_instance_id,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            max_uses=max_uses,
            created_by_id=created_by_id,
        )

    @property
    def is_valid(self) -> bool:
        """Check if token is still valid."""
        if self.is_revoked:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        if self.max_uses and self.use_count >= self.max_uses:
            return False
        return True

    def record_use(self) -> None:
        """Record a use of this token."""
        now = datetime.utcnow()
        self.use_count += 1
        self.last_used_at = now
        if not self.first_used_at:
            self.first_used_at = now

    def revoke(self, reason: str = None) -> None:
        """Revoke this token."""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason
