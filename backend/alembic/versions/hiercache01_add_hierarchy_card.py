"""Add contracts.hierarchy_card — cached hierarchy-detection document card.

Revision ID: hiercache01
Revises: usagemeter01
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'hiercache01'
down_revision: Union[str, None] = 'usagemeter01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'contracts',
        sa.Column('hierarchy_card', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('contracts', 'hierarchy_card')
