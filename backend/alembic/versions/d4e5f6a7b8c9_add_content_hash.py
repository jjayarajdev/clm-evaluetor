"""Add content_hash column to contracts

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-01 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add content_hash column for duplicate detection."""
    op.add_column(
        'contracts',
        sa.Column('content_hash', sa.String(64), nullable=True)
    )
    op.create_index('ix_contracts_content_hash', 'contracts', ['content_hash'])


def downgrade() -> None:
    """Remove content_hash column."""
    op.drop_index('ix_contracts_content_hash', table_name='contracts')
    op.drop_column('contracts', 'content_hash')
