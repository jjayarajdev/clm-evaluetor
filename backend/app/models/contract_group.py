"""Contract groups — user-facing families of related contracts.

Three group types:
- manual: user-created, arbitrary membership
- upload_batch: created from a batch upload with a group name
- auto_family: materialized from the ContractLink graph (one per connected
  component, anchored at the root contract) by services/group_sync.py
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contract import Contract
    from app.models.user import User


GROUP_TYPES = ("manual", "upload_batch", "auto_family")
MEMBER_SOURCES = ("manual", "upload_batch", "auto_family")
FINDING_STATUSES = ("open", "resolved", "dismissed")


class ContractGroup(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """A named set of related contracts, optionally nested."""

    __tablename__ = "contract_groups"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    group_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )

    # Nesting (groups of groups)
    parent_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Responsible person (alert routing — Phase 3)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Anchor contract for auto_family groups (the root of the link tree)
    root_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Batch that created an upload_batch group
    upload_batch_id: Mapped[str | None] = mapped_column(String(100), index=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    parent_group: Mapped["ContractGroup | None"] = relationship(
        "ContractGroup",
        remote_side="ContractGroup.id",
        back_populates="child_groups",
    )
    child_groups: Mapped[list["ContractGroup"]] = relationship(
        "ContractGroup",
        back_populates="parent_group",
    )
    members: Mapped[list["ContractGroupMember"]] = relationship(
        "ContractGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )
    owner: Mapped["User | None"] = relationship(
        "User", foreign_keys=[owner_user_id]
    )
    root_contract: Mapped["Contract | None"] = relationship(
        "Contract", foreign_keys=[root_contract_id]
    )

    __table_args__ = (
        # One auto_family group per root contract, one group per upload batch
        Index(
            "uq_contract_groups_auto_root",
            "tenant_id",
            "root_contract_id",
            unique=True,
            postgresql_where="group_type = 'auto_family'",
        ),
        Index(
            "uq_contract_groups_batch",
            "tenant_id",
            "upload_batch_id",
            unique=True,
            postgresql_where="group_type = 'upload_batch'",
        ),
    )

    def __repr__(self) -> str:
        return f"<ContractGroup {self.group_type}: {self.name}>"


class ContractGroupMember(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Membership of a contract in a group, with provenance."""

    __tablename__ = "contract_group_members"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Why this contract is in the group; auto-family sync only reconciles
    # its own rows so manual pins survive recomputes.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    added_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    group: Mapped["ContractGroup"] = relationship(
        "ContractGroup", back_populates="members"
    )
    contract: Mapped["Contract"] = relationship("Contract")

    __table_args__ = (
        UniqueConstraint("group_id", "contract_id", name="uq_group_member"),
    )

    def __repr__(self) -> str:
        return f"<ContractGroupMember {self.group_id} ← {self.contract_id} ({self.source})>"


class ContractGroupFinding(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """A completeness finding for a group/contract.

    Phase 2 populates these: e.g. an MSA references "Schedule A" but no
    matching document exists in the system (finding_type='missing_reference').
    """

    __tablename__ = "contract_group_findings"

    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # The contract whose text references the missing document
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    finding_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="missing_reference"
    )
    reference_label: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    resolved_by_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    dismissed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "contract_id", "reference_label",
            name="uq_group_finding_reference",
        ),
        Index("ix_group_findings_status", "group_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<ContractGroupFinding {self.finding_type}: {self.reference_label} ({self.status})>"
