"""Add 'other' to clausetype enum

Revision ID: t3u4v5w6x7y8
Revises: s2t3u4v5w6x7
Create Date: 2026-02-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 't3u4v5w6x7y8'
down_revision: Union[str, None] = 's2t3u4v5w6x7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'other' to clausetype enum - this is the catch-all type
    # that was in the Python enum but missing from migrations
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'other'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values easily
    pass
