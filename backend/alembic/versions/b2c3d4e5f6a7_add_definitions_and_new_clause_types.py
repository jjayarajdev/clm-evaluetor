"""Add contract_definitions table and new clause types

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-01 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new enum values to clausetype
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'preamble'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'definitions'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'service_order'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'procedural'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'exhibit'")

    # Create contract_definitions table
    op.create_table(
        'contract_definitions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('source_clause_id', sa.UUID(), nullable=True),
        sa.Column('term', sa.String(length=255), nullable=False),
        sa.Column('term_normalized', sa.String(length=255), nullable=False),
        sa.Column('definition_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('section_reference', sa.String(length=50), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('cross_references', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_clause_id'], ['clauses.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_definitions_contract_id', 'contract_definitions', ['contract_id'])
    op.create_index('ix_definitions_term', 'contract_definitions', ['term'])
    op.create_index('ix_definitions_term_normalized', 'contract_definitions', ['term_normalized'])
    op.create_index('ix_definitions_contract_term', 'contract_definitions', ['contract_id', 'term_normalized'])
    op.create_index('ix_definitions_category', 'contract_definitions', ['category'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop contract_definitions table
    op.drop_index('ix_definitions_category', table_name='contract_definitions')
    op.drop_index('ix_definitions_contract_term', table_name='contract_definitions')
    op.drop_index('ix_definitions_term_normalized', table_name='contract_definitions')
    op.drop_index('ix_definitions_term', table_name='contract_definitions')
    op.drop_index('ix_definitions_contract_id', table_name='contract_definitions')
    op.drop_table('contract_definitions')

    # Note: PostgreSQL doesn't support removing enum values easily
    # The new clause type enum values will remain
