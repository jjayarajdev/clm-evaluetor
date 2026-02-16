"""Metric Snapshot model for historical tracking."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MetricSnapshot(Base):
    """Daily snapshot of key metrics for trend analysis."""

    __tablename__ = "metric_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Snapshot date (one record per day)
    snapshot_date = Column(Date, nullable=False, index=True)

    # Contract metrics
    total_contracts = Column(Integer, nullable=False, default=0)
    contracts_at_risk = Column(Integer, nullable=False, default=0)
    total_contract_value = Column(Numeric(15, 2), nullable=False, default=0)

    # Compliance metrics
    compliance_rate = Column(Numeric(5, 2), nullable=False, default=0)  # Percentage
    obligations_total = Column(Integer, nullable=False, default=0)
    obligations_completed = Column(Integer, nullable=False, default=0)
    obligations_overdue = Column(Integer, nullable=False, default=0)

    # SLA metrics
    sla_compliance_rate = Column(Numeric(5, 2), nullable=False, default=0)  # Percentage
    slas_total = Column(Integer, nullable=False, default=0)
    slas_breached = Column(Integer, nullable=False, default=0)

    # Renewal metrics
    renewals_due_30_days = Column(Integer, nullable=False, default=0)
    renewals_due_60_days = Column(Integer, nullable=False, default=0)
    renewals_due_90_days = Column(Integer, nullable=False, default=0)

    # Vendor metrics
    total_vendors = Column(Integer, nullable=False, default=0)
    vendors_at_risk = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_metric_snapshot_date_unique', 'snapshot_date', unique=True),
    )

    def __repr__(self):
        return f"<MetricSnapshot {self.snapshot_date}>"
