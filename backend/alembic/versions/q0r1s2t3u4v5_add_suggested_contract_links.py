"""Add suggested contract links table

Revision ID: q0r1s2t3u4v5
Revises: p9q0r1s2t3u4
Create Date: 2026-02-22

This migration adds the suggested_contract_links table for AI-detected
relationship suggestions that require user approval before becoming actual links.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'q0r1s2t3u4v5'
down_revision: Union[str, None] = 'p9q0r1s2t3u4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for suggestion status using raw SQL
    # This avoids SQLAlchemy's enum handling issues with asyncpg
    op.execute("CREATE TYPE suggestionstatus AS ENUM ('pending', 'approved', 'rejected', 'expired')")

    # Create suggested_contract_links table
    # Use postgresql.ENUM with create_type=False since we created it above
    from sqlalchemy.dialects.postgresql import ENUM
    suggestionstatus_enum = ENUM('pending', 'approved', 'rejected', 'expired', name='suggestionstatus', create_type=False)

    op.create_table(
        'suggested_contract_links',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),

        # Source and target contracts
        sa.Column('source_contract_id', UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_contract_id', UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),

        # Suggested relationship
        sa.Column('suggested_link_type', sa.String(50), nullable=False, server_default='related'),
        sa.Column('suggested_direction', sa.String(20), nullable=False, server_default='source_is_child'),

        # Confidence and reasoning
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('matching_signals', JSONB(), nullable=True),

        # Status - use the pre-created enum with create_type=False
        sa.Column('status', suggestionstatus_enum, nullable=False, server_default='pending'),

        # Review details
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),

        # Created link reference
        sa.Column('created_link_id', UUID(as_uuid=True), sa.ForeignKey('contract_links.id', ondelete='SET NULL'), nullable=True),

        # Batch grouping
        sa.Column('batch_id', sa.String(100), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes for efficient querying
    op.create_index('ix_suggested_contract_links_source', 'suggested_contract_links', ['source_contract_id'])
    op.create_index('ix_suggested_contract_links_target', 'suggested_contract_links', ['target_contract_id'])
    op.create_index('ix_suggested_contract_links_status', 'suggested_contract_links', ['status'])
    op.create_index('ix_suggested_contract_links_tenant_status', 'suggested_contract_links', ['tenant_id', 'status'])
    op.create_index('ix_suggested_contract_links_batch', 'suggested_contract_links', ['batch_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_suggested_contract_links_batch', table_name='suggested_contract_links')
    op.drop_index('ix_suggested_contract_links_tenant_status', table_name='suggested_contract_links')
    op.drop_index('ix_suggested_contract_links_status', table_name='suggested_contract_links')
    op.drop_index('ix_suggested_contract_links_target', table_name='suggested_contract_links')
    op.drop_index('ix_suggested_contract_links_source', table_name='suggested_contract_links')

    # Drop table
    op.drop_table('suggested_contract_links')

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS suggestionstatus")
