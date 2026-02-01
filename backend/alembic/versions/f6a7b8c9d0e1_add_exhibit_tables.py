"""Add exhibit tables

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-01 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add contract_exhibits and exhibit_fee_items tables."""
    # Create exhibit type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE exhibittype AS ENUM ('schedule', 'exhibit', 'appendix', 'annexure', 'attachment', 'pricing', 'sow', 'other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create contract_exhibits table
    op.execute("""
        CREATE TABLE contract_exhibits (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            source_clause_id UUID REFERENCES clauses(id) ON DELETE SET NULL,
            exhibit_identifier VARCHAR(50) NOT NULL,
            exhibit_type exhibittype NOT NULL DEFAULT 'exhibit',
            title VARCHAR(500),
            description TEXT,
            page_number INTEGER,
            source_text TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)

    op.create_index('ix_exhibits_contract', 'contract_exhibits', ['contract_id'])
    op.create_index('ix_exhibits_type', 'contract_exhibits', ['exhibit_type'])

    # Create exhibit_fee_items table
    op.create_table(
        'exhibit_fee_items',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('exhibit_id', sa.UUID(), nullable=False),
        sa.Column('item_name', sa.String(500), nullable=False),
        sa.Column('item_description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('unit_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('total_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('item_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['exhibit_id'], ['contract_exhibits.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_fee_items_exhibit', 'exhibit_fee_items', ['exhibit_id'])


def downgrade() -> None:
    """Remove exhibit tables."""
    op.drop_index('ix_fee_items_exhibit', table_name='exhibit_fee_items')
    op.drop_table('exhibit_fee_items')
    op.drop_index('ix_exhibits_type', table_name='contract_exhibits')
    op.drop_index('ix_exhibits_contract', table_name='contract_exhibits')
    op.drop_table('contract_exhibits')
    op.execute("DROP TYPE IF EXISTS exhibittype")
