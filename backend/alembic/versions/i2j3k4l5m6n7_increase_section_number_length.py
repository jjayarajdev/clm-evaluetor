"""Increase section_number column length

Revision ID: i2j3k4l5m6n7
Revises: h1i2j3k4l5m6
Create Date: 2026-02-12 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'i2j3k4l5m6n7'
down_revision: Union[str, Sequence[str], None] = 'h1i2j3k4l5m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Increase section_number from VARCHAR(50) to VARCHAR(255)."""
    op.alter_column(
        'clauses',
        'section_number',
        type_=sa.String(255),
        existing_type=sa.String(50),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Revert section_number back to VARCHAR(50)."""
    op.alter_column(
        'clauses',
        'section_number',
        type_=sa.String(50),
        existing_type=sa.String(255),
        existing_nullable=True,
    )
