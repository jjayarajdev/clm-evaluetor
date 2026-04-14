"""Add dashboard_cache table and tenant_id to metric_snapshots

Revision ID: a0b1c2d3e4f5
Revises: z9a0b1c2d3e4
Create Date: 2026-04-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, None] = 'z9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tenant_id to metric_snapshots
    op.add_column('metric_snapshots',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_metric_snapshots_tenant',
        'metric_snapshots', 'tenants',
        ['tenant_id'], ['id']
    )
    # Replace old unique index (date-only) with tenant+date
    op.drop_index('ix_metric_snapshot_date_unique', table_name='metric_snapshots')
    op.create_index(
        'ix_metric_snapshot_tenant_date',
        'metric_snapshots',
        ['tenant_id', 'snapshot_date'],
        unique=True,
    )

    # Create dashboard_cache table
    op.create_table(
        'dashboard_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('dashboard_type', sa.String(50), nullable=False),
        sa.Column('cache_key', sa.String(255), nullable=True, server_default=''),
        sa.Column('data', postgresql.JSONB(), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_dashboard_cache_tenant'),
    )
    op.create_index(
        'ix_dashboard_cache_lookup',
        'dashboard_cache',
        ['tenant_id', 'dashboard_type', 'cache_key'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_dashboard_cache_lookup', table_name='dashboard_cache')
    op.drop_table('dashboard_cache')

    op.drop_index('ix_metric_snapshot_tenant_date', table_name='metric_snapshots')
    op.create_index(
        'ix_metric_snapshot_date_unique',
        'metric_snapshots',
        ['snapshot_date'],
        unique=True,
    )
    op.drop_constraint('fk_metric_snapshots_tenant', 'metric_snapshots', type_='foreignkey')
    op.drop_column('metric_snapshots', 'tenant_id')
