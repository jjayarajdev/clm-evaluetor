"""Add notification rules table.

Revision ID: y8z9a0b1c2d3
Revises: x7y8z9a0b1c2
Create Date: 2024-03-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'y8z9a0b1c2d3'
down_revision: Union[str, None] = 'x7y8z9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create rule event type enum (only if not exists)
    # Using a raw connection to handle the check
    from sqlalchemy import text
    conn = op.get_bind()

    # Check if enum already exists
    result = conn.execute(text(
        "SELECT 1 FROM pg_type WHERE typname = 'ruleeventtype'"
    ))
    enum_exists = result.fetchone() is not None

    if not enum_exists:
        op.execute("""
            CREATE TYPE ruleeventtype AS ENUM (
                'contract_expiration',
                'notice_deadline',
                'obligation_due',
                'sla_breach',
                'sla_warning',
                'renewal_reminder',
                'key_date',
                'compliance_overdue'
            )
        """)

    # Create notification rules table using postgresql.ENUM for the pre-created type
    ruleeventtype = postgresql.ENUM(
        'contract_expiration', 'notice_deadline', 'obligation_due',
        'sla_breach', 'sla_warning', 'renewal_reminder', 'key_date',
        'compliance_overdue',
        name='ruleeventtype',
        create_type=False
    )

    op.create_table(
        'notification_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('event_type', ruleeventtype, nullable=False),
        sa.Column('days_before', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('repeat_interval_days', sa.Integer(), nullable=True),
        sa.Column('max_repeats', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('channels', sa.JSON(), nullable=False, server_default='["email"]'),
        sa.Column('notify_contract_owner', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('additional_recipients', sa.JSON(), nullable=True),
        sa.Column('contract_types', sa.JSON(), nullable=True),
        sa.Column('min_contract_value', sa.Float(), nullable=True),
        sa.Column('risk_levels', sa.JSON(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=False, server_default='normal'),
        sa.Column('respect_business_hours', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('business_hours_start', sa.Time(), nullable=True),
        sa.Column('business_hours_end', sa.Time(), nullable=True),
        sa.Column('email_template', sa.String(100), nullable=True),
        sa.Column('last_triggered', sa.DateTime(), nullable=True),
        sa.Column('trigger_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('ix_notification_rules_tenant_id', 'notification_rules', ['tenant_id'])
    op.create_index('ix_notification_rules_event_type', 'notification_rules', ['event_type'])
    op.create_index('ix_notification_rules_is_active', 'notification_rules', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_notification_rules_is_active', 'notification_rules')
    op.drop_index('ix_notification_rules_event_type', 'notification_rules')
    op.drop_index('ix_notification_rules_tenant_id', 'notification_rules')
    op.drop_table('notification_rules')
    op.execute("DROP TYPE IF EXISTS ruleeventtype")
