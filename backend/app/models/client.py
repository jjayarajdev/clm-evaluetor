"""Client model for organizing contracts by client/organization."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Client(Base):
    """Client/Organization that contracts belong to."""

    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant (multi-tenancy)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # Required fields
    name = Column(String(255), nullable=False)  # Full name: "ING Bank N.V."
    code = Column(String(50), nullable=False, unique=True)  # Short code: "ING"

    # Optional contact/company info
    industry = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    # Optional primary contact
    contact_name = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    contact_title = Column(String(100), nullable=True)

    # Notes and metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    contracts = relationship("Contract", back_populates="client", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Client {self.code}: {self.name}>"

    @property
    def contract_count(self) -> int:
        """Get number of contracts for this client."""
        return self.contracts.count()
