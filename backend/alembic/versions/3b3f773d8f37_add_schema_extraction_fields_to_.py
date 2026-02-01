"""Add schema extraction fields to contracts

Revision ID: 3b3f773d8f37
Revises: a94bb936193e
Create Date: 2026-02-01 11:19:39.797154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3b3f773d8f37'
down_revision: Union[str, Sequence[str], None] = 'a94bb936193e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add fields for schema-based extraction."""
    # Add extracted_text column for storing raw OCR/parsed text
    op.add_column(
        'contracts',
        sa.Column('extracted_text', sa.Text(), nullable=True)
    )

    # Add schema_data column for storing structured extraction results
    op.add_column(
        'contracts',
        sa.Column('schema_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # Add schema_id column for tracking which schema was used
    op.add_column(
        'contracts',
        sa.Column('schema_id', sa.String(100), nullable=True)
    )


def downgrade() -> None:
    """Remove schema extraction fields."""
    op.drop_column('contracts', 'schema_id')
    op.drop_column('contracts', 'schema_data')
    op.drop_column('contracts', 'extracted_text')
