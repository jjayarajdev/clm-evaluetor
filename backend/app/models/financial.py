"""Contract financial terms model - fees, payments, penalties, liability."""

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contract import Contract


class FeeType(str, enum.Enum):
    """Types of fees in contracts."""

    BASE_FEE = "base_fee"
    PER_UNIT = "per_unit"
    PER_HOUR = "per_hour"
    PER_DAY = "per_day"
    PERCENTAGE = "percentage"
    MILESTONE = "milestone"
    RECURRING_MONTHLY = "recurring_monthly"
    RECURRING_ANNUAL = "recurring_annual"
    ONE_TIME = "one_time"
    RETAINER = "retainer"
    SUCCESS_FEE = "success_fee"
    LICENSING_FEE = "licensing_fee"
    MAINTENANCE_FEE = "maintenance_fee"
    SUPPORT_FEE = "support_fee"
    OTHER = "other"


class PaymentTerms(str, enum.Enum):
    """Standard payment terms."""

    UPON_RECEIPT = "upon_receipt"
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_45 = "net_45"
    NET_60 = "net_60"
    NET_90 = "net_90"
    ADVANCE = "advance"
    MILESTONE_BASED = "milestone_based"
    UPON_COMPLETION = "upon_completion"
    CUSTOM = "custom"


class PenaltyType(str, enum.Enum):
    """Types of penalties."""

    LATE_PAYMENT = "late_payment"
    LATE_DELIVERY = "late_delivery"
    NON_COMPLIANCE = "non_compliance"
    BREACH = "breach"
    EARLY_TERMINATION = "early_termination"
    SLA_VIOLATION = "sla_violation"
    QUALITY_FAILURE = "quality_failure"
    OTHER = "other"


class LiabilityCapType(str, enum.Enum):
    """Types of liability caps."""

    NONE = "none"
    UNLIMITED = "unlimited"
    FIXED_AMOUNT = "fixed_amount"
    FEES_PAID = "fees_paid"
    ANNUAL_FEES = "annual_fees"
    MULTIPLE_OF_FEES = "multiple_of_fees"
    PERCENTAGE_OF_VALUE = "percentage_of_value"
    INSURANCE_LIMIT = "insurance_limit"
    CUSTOM = "custom"


class ContractFinancial(Base, UUIDMixin, TimestampMixin):
    """Financial terms for a contract - fees, payments, penalties."""

    __tablename__ = "contract_financials"

    # Foreign key to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Fee details
    fee_type: Mapped[FeeType] = mapped_column(
        Enum(FeeType, name='feetype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=FeeType.OTHER,
    )
    fee_description: Mapped[str | None] = mapped_column(String(500))
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str | None] = mapped_column(String(3), default="USD")
    quantity: Mapped[int | None] = mapped_column()
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    # Payment terms
    payment_terms: Mapped[PaymentTerms | None] = mapped_column(
        Enum(PaymentTerms, name='paymentterms', create_type=False, values_callable=lambda x: [e.value for e in x]),
    )
    payment_terms_days: Mapped[int | None] = mapped_column()
    payment_trigger: Mapped[str | None] = mapped_column(String(255))
    invoicing_frequency: Mapped[str | None] = mapped_column(String(100))

    # Penalty details (if this record is a penalty)
    is_penalty: Mapped[bool] = mapped_column(Boolean, default=False)
    penalty_type: Mapped[PenaltyType | None] = mapped_column(
        Enum(PenaltyType, name='penaltytype', create_type=False, values_callable=lambda x: [e.value for e in x]),
    )
    penalty_trigger: Mapped[str | None] = mapped_column(Text)
    penalty_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    penalty_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Section reference
    section_reference: Mapped[str | None] = mapped_column(String(100))

    # Relationship
    contract: Mapped["Contract"] = relationship(back_populates="financials")

    def __repr__(self) -> str:
        return f"<ContractFinancial {self.fee_type.value}: {self.fee_amount} {self.currency}>"


class ContractLiability(Base, UUIDMixin, TimestampMixin):
    """Liability and indemnification terms for a contract."""

    __tablename__ = "contract_liabilities"

    # Foreign key to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Liability cap
    liability_cap_type: Mapped[LiabilityCapType | None] = mapped_column(
        Enum(LiabilityCapType, name='liabilitycaptype', create_type=False, values_callable=lambda x: [e.value for e in x]),
    )
    liability_cap_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    liability_cap_currency: Mapped[str | None] = mapped_column(String(3), default="USD")
    liability_cap_description: Mapped[str | None] = mapped_column(Text)
    liability_cap_multiplier: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Exclusions
    excludes_direct_damages: Mapped[bool | None] = mapped_column(Boolean)
    excludes_indirect_damages: Mapped[bool | None] = mapped_column(Boolean)
    excludes_consequential_damages: Mapped[bool | None] = mapped_column(Boolean)
    excludes_lost_profits: Mapped[bool | None] = mapped_column(Boolean)
    exclusions_description: Mapped[str | None] = mapped_column(Text)

    # Indemnification
    indemnifying_party: Mapped[str | None] = mapped_column(String(255))
    indemnified_party: Mapped[str | None] = mapped_column(String(255))
    indemnification_scope: Mapped[str | None] = mapped_column(Text)
    mutual_indemnification: Mapped[bool | None] = mapped_column(Boolean)

    # Insurance requirements
    insurance_required: Mapped[bool | None] = mapped_column(Boolean)
    insurance_types: Mapped[str | None] = mapped_column(Text)  # JSON array as text
    insurance_minimum_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))

    # Section reference
    section_reference: Mapped[str | None] = mapped_column(String(100))

    # Relationship
    contract: Mapped["Contract"] = relationship(back_populates="liabilities")

    def __repr__(self) -> str:
        return f"<ContractLiability cap={self.liability_cap_type}>"
