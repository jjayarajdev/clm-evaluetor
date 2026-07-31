"""Add usage_events table and contracts.page_count (LLM/usage metering phase 1).

Revision ID: usagemeter01
Revises: oblassign01
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'usagemeter01'
down_revision: Union[str, None] = 'oblassign01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usage_events',
        sa.Column('id', sa.UUID(), nullable=False),
        # Nullable: platform-level calls without tenant context are still metered
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('metric', sa.String(40), nullable=False),
        sa.Column('quantity', sa.BigInteger(), nullable=False),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('ref_type', sa.String(40), nullable=True),
        sa.Column('ref_id', sa.UUID(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_usage_events_tenant_id', 'usage_events', ['tenant_id'])
    op.create_index('ix_usage_events_metric', 'usage_events', ['metric'])
    op.create_index('ix_usage_events_tenant_occurred', 'usage_events', ['tenant_id', 'occurred_at'])

    op.add_column('contracts', sa.Column('page_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('contracts', 'page_count')
    op.drop_index('ix_usage_events_tenant_occurred', table_name='usage_events')
    op.drop_index('ix_usage_events_metric', table_name='usage_events')
    op.drop_index('ix_usage_events_tenant_id', table_name='usage_events')
    op.drop_table('usage_events')
