"""Add metric_snapshots table for historical tracking

Revision ID: n7o8p9q0r1s2
Revises: m6n7o8p9q0r1
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'n7o8p9q0r1s2'
down_revision: Union[str, None] = 'm6n7o8p9q0r1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'metric_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        # Contract metrics
        sa.Column('total_contracts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('contracts_at_risk', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_contract_value', sa.Numeric(15, 2), nullable=False, server_default='0'),
        # Compliance metrics
        sa.Column('compliance_rate', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('obligations_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('obligations_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('obligations_overdue', sa.Integer(), nullable=False, server_default='0'),
        # SLA metrics
        sa.Column('sla_compliance_rate', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('slas_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('slas_breached', sa.Integer(), nullable=False, server_default='0'),
        # Renewal metrics
        sa.Column('renewals_due_30_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('renewals_due_60_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('renewals_due_90_days', sa.Integer(), nullable=False, server_default='0'),
        # Vendor metrics
        sa.Column('total_vendors', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('vendors_at_risk', sa.Integer(), nullable=False, server_default='0'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_metric_snapshots_date', 'metric_snapshots', ['snapshot_date'])
    op.create_index('ix_metric_snapshot_date_unique', 'metric_snapshots', ['snapshot_date'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_metric_snapshot_date_unique', table_name='metric_snapshots')
    op.drop_index('ix_metric_snapshots_date', table_name='metric_snapshots')
    op.drop_table('metric_snapshots')
