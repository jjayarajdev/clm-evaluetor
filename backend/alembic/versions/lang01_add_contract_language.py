"""Add contracts.language (ISO 639-1, detected at ingestion).

Backing for language-aware extraction: agents write free-text output in the
document's language instead of defaulting to English.

Revision ID: lang01
Revises: rbacdb01
Create Date: 2026-08-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'lang01'
down_revision: Union[str, None] = 'rbacdb01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contracts', sa.Column('language', sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column('contracts', 'language')
