"""Contract Party model for storing party information."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class PartyRole(str, enum.Enum):
    """Role of a party in a contract."""

    PROVIDER = "provider"
    CLIENT = "client"
    VENDOR = "vendor"
    CUSTOMER = "customer"
    LICENSOR = "licensor"
    LICENSEE = "licensee"
    EMPLOYER = "employer"
    EMPLOYEE = "employee"
    DISCLOSING_PARTY = "disclosing_party"
    RECEIVING_PARTY = "receiving_party"
    OTHER = "other"


class ContractParty(Base, UUIDMixin, TimestampMixin):
    """Party to a contract (company, individual, etc.)."""

    __tablename__ = "contract_parties"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Party details
    role: Mapped[PartyRole] = mapped_column(
        Enum(PartyRole, name='partyrole', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PartyRole.OTHER,
    )
    legal_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    short_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    jurisdiction: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    registered_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Is this the "our company" side or the counterparty?
    is_primary: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Source reference
    section_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationship back to contract
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="parties",
    )

    # Indexes
    __table_args__ = (
        Index("ix_contract_parties_contract_role", "contract_id", "role"),
        Index("ix_contract_parties_legal_name", "legal_name"),
    )

    def __repr__(self) -> str:
        return f"<ContractParty {self.role.value}: {self.legal_name}>"
