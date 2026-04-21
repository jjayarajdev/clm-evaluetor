"""Add sharepoint to IntegrationSystem enum.

Revision ID: sp01_add_sharepoint_enum
Revises: eq02_global_golden_set
Create Date: 2026-04-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = "sp01_add_sharepoint_enum"
down_revision: str = "eq02_global_golden_set"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE integrationsystem ADD VALUE IF NOT EXISTS 'sharepoint'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values — no-op
    pass
