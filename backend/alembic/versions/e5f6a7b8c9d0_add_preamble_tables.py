"""Add preamble tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-01 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add contract_preambles and contract_party_details tables."""
    # Create contract_preambles table
    op.create_table(
        'contract_preambles',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('document_title', sa.String(500), nullable=True),
        sa.Column('effective_date_text', sa.String(200), nullable=True),
        sa.Column('background_summary', sa.Text(), nullable=True),
        sa.Column('recitals_text', sa.Text(), nullable=True),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('contract_id'),
    )
    op.create_index('ix_preambles_contract', 'contract_preambles', ['contract_id'])

    # Create contract_party_details table
    op.create_table(
        'contract_party_details',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('preamble_id', sa.UUID(), nullable=False),
        sa.Column('party_name', sa.String(255), nullable=False),
        sa.Column('party_role', sa.String(100), nullable=True),
        sa.Column('party_short_name', sa.String(100), nullable=True),
        sa.Column('legal_form', sa.String(100), nullable=True),
        sa.Column('jurisdiction_of_incorporation', sa.String(100), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('party_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['preamble_id'], ['contract_preambles.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_party_details_preamble', 'contract_party_details', ['preamble_id'])
    op.create_index('ix_party_details_name', 'contract_party_details', ['party_name'])


def downgrade() -> None:
    """Remove preamble tables."""
    op.drop_index('ix_party_details_name', table_name='contract_party_details')
    op.drop_index('ix_party_details_preamble', table_name='contract_party_details')
    op.drop_table('contract_party_details')
    op.drop_index('ix_preambles_contract', table_name='contract_preambles')
    op.drop_table('contract_preambles')
