"""Add golden set and extraction verification tables

Revision ID: eq01_extraction_quality
Revises: dc01_dashboard_cache
Create Date: 2026-04-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'eq01_extraction_quality'
down_revision: Union[str, None] = 'dc01_dashboard_cache'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'golden_set_contracts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('added_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_baseline', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('metadata_score', sa.Float(), nullable=True),
        sa.Column('clause_score', sa.Float(), nullable=True),
        sa.Column('obligation_score', sa.Float(), nullable=True),
        sa.Column('sla_score', sa.Float(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_golden_set_tenant'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], name='fk_golden_set_contract', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'], name='fk_golden_set_added_by'),
    )
    op.create_index('ix_golden_set_tenant_contract', 'golden_set_contracts', ['tenant_id', 'contract_id'], unique=True)

    op.create_table(
        'extraction_verifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('golden_set_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('corrected_value', postgresql.JSONB(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['golden_set_id'], ['golden_set_contracts.id'], name='fk_verification_golden_set', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], name='fk_verification_user'),
    )
    op.create_index('ix_verification_golden_set', 'extraction_verifications', ['golden_set_id'])
    op.create_index('ix_verification_entity', 'extraction_verifications', ['golden_set_id', 'entity_type', 'entity_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_verification_entity', table_name='extraction_verifications')
    op.drop_index('ix_verification_golden_set', table_name='extraction_verifications')
    op.drop_table('extraction_verifications')
    op.drop_index('ix_golden_set_tenant_contract', table_name='golden_set_contracts')
    op.drop_table('golden_set_contracts')
