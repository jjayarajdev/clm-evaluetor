"""SLA (Service Level Agreement) models for tracking and breach detection."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SLAMetricType(str, enum.Enum):
    """Types of SLA metrics."""

    # Availability metrics
    UPTIME_PERCENTAGE = "uptime_percentage"  # e.g., 99.9% uptime
    AVAILABILITY = "availability"  # e.g., available 24/7

    # Time-based metrics
    RESPONSE_TIME = "response_time"  # e.g., respond within 4 hours
    RESOLUTION_TIME = "resolution_time"  # e.g., resolve within 24 hours
    DELIVERY_TIME = "delivery_time"  # e.g., deliver within 5 business days

    # Rate/percentage metrics
    SUCCESS_RATE = "success_rate"  # e.g., first call resolution 75%, change success 98%
    ERROR_RATE = "error_rate"  # e.g., less than 0.1% errors
    COMPLIANCE_RATE = "compliance_rate"  # e.g., patch compliance >98%

    # Capacity/utilization metrics
    UTILIZATION = "utilization"  # e.g., CPU <70%, memory <75%, storage <80%
    THROUGHPUT = "throughput"  # e.g., process 1000 transactions/hour

    # Recovery metrics
    RECOVERY_TIME = "recovery_time"  # e.g., RTO 4 hours, restore within 8 hours
    RECOVERY_POINT = "recovery_point"  # e.g., RPO 1 hour (max data loss)

    # Quality metrics
    QUALITY_SCORE = "quality_score"  # e.g., CSAT 4.5/5, NPS > 50

    # Fallback
    CUSTOM = "custom"


class SLAUnit(str, enum.Enum):
    """Units for SLA measurements."""

    PERCENTAGE = "percentage"
    HOURS = "hours"
    MINUTES = "minutes"
    DAYS = "days"
    BUSINESS_DAYS = "business_days"
    COUNT = "count"
    SCORE = "score"


class SLASeverity(str, enum.Enum):
    """Severity levels for SLA breaches."""

    CRITICAL = "critical"  # P1 - Immediate attention
    HIGH = "high"  # P2 - Same day
    MEDIUM = "medium"  # P3 - Within 48 hours
    LOW = "low"  # P4 - Best effort


class BreachSeverity(str, enum.Enum):
    """Severity of an SLA breach based on deviation."""

    MINOR = "minor"  # <5% deviation
    MODERATE = "moderate"  # 5-15% deviation
    MAJOR = "major"  # 15-30% deviation
    CRITICAL = "critical"  # >30% deviation


class ContractSLA(Base, UUIDMixin, TimestampMixin):
    """SLA terms extracted from a contract."""

    __tablename__ = "contract_slas"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="slas",
    )

    # Relationship to source clause (optional)
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
    )

    # SLA identification
    sla_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    sla_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Contract reference (from Service Level Matrix)
    section_reference: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # e.g., "2.1.1", "12.1"
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., "Critical Service Levels", "Key Measurements"
    service_tower: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., "Desktop Services", "Network Services"

    # Metric details
    metric_type: Mapped[SLAMetricType] = mapped_column(
        Enum(SLAMetricType, name='slametrictype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SLAMetricType.CUSTOM,
    )
    metric_unit: Mapped[SLAUnit] = mapped_column(
        Enum(SLAUnit, name='slaunit', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SLAUnit.PERCENTAGE,
    )

    # Target values
    target_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    target_operator: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=">=",  # >=, <=, =, >, <
    )
    warning_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )  # Amber threshold

    # Severity and priority
    severity: Mapped[SLASeverity] = mapped_column(
        Enum(SLASeverity, name='slaseverity', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SLASeverity.MEDIUM,
    )

    # Penalty information
    has_penalty: Mapped[bool] = mapped_column(Boolean, default=False)
    penalty_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # percentage, fixed, credit
    penalty_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    penalty_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_penalty_cap: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # At-risk and earnback (from IT outsourcing contracts)
    at_risk_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )  # Pool percentage allocation for this SLA
    earnback_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    earnback_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    minimum_service_level: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True
    )  # Floor value below which default occurs

    # Measurement period
    measurement_period: Mapped[str | None] = mapped_column(String(50), nullable=True)  # monthly, quarterly, annual
    measurement_start: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    current_compliance_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)  # 0-100
    last_measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_breaches: Mapped[int] = mapped_column(Integer, default=0)

    # Source text
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    performances: Mapped[list["SLAPerformance"]] = relationship(
        "SLAPerformance",
        back_populates="sla",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_sla_contract_metric", "contract_id", "metric_type"),
        Index("ix_sla_severity", "severity"),
        Index("ix_sla_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<ContractSLA {self.sla_name} ({self.metric_type.value})>"


class SLAPerformance(Base, UUIDMixin, TimestampMixin):
    """Recorded SLA performance measurements."""

    __tablename__ = "sla_performances"

    # Relationship to SLA
    sla_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_slas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sla: Mapped["ContractSLA"] = relationship(
        "ContractSLA",
        back_populates="performances",
    )

    # Measurement
    actual_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    measurement_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    measurement_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Compliance status
    is_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    deviation_percentage: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    breach_severity: Mapped[BreachSeverity | None] = mapped_column(
        Enum(BreachSeverity, name='breachseverity', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )

    # Penalty applied
    penalty_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    penalty_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    credit_issued: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_sla_perf_sla_date", "sla_id", "measured_at"),
        Index("ix_sla_perf_compliant", "is_compliant"),
        Index("ix_sla_perf_breach", "breach_severity"),
    )

    def __repr__(self) -> str:
        status = "✓" if self.is_compliant else "✗"
        return f"<SLAPerformance {status} {self.actual_value} @ {self.measured_at}>"
