"""Metric Snapshot and Dashboard Cache models for performance optimization."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, Index, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class MetricSnapshot(Base):
    """Daily snapshot of key metrics for trend analysis, per tenant."""

    __tablename__ = "metric_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)

    # Snapshot date (one record per tenant per day)
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
        Index('ix_metric_snapshot_tenant_date', 'tenant_id', 'snapshot_date', unique=True),
    )

    def __repr__(self):
        return f"<MetricSnapshot tenant={self.tenant_id} {self.snapshot_date}>"


class DashboardCache(Base):
    """Pre-computed dashboard responses stored as JSON.

    Cache-through pattern: dashboard endpoints check cache first,
    compute on miss, store result. Invalidated on data mutations.
    """

    __tablename__ = "dashboard_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)

    # Cache key: dashboard type (admin, legal, procurement, portfolio, etc.)
    dashboard_type = Column(String(50), nullable=False)

    # Optional sub-key for filtered views (e.g., bu_id, contract_id)
    cache_key = Column(String(255), nullable=True, default="")

    # Pre-computed response as JSON
    data = Column(JSONB, nullable=False)

    # Cache validity
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_dashboard_cache_lookup', 'tenant_id', 'dashboard_type', 'cache_key', unique=True),
    )
