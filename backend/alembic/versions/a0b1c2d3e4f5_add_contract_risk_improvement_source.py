"""Add contract_risk to improvementsource enum.

Revision ID: a0b1c2d3e4f5
Revises: fg05_snowslasync
Create Date: 2026-03-26 10:00:00.000000
"""

from alembic import op

# revision identifiers
revision = "a0b1c2d3e4f5"
down_revision = "fg05_snowslasync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE improvementsource ADD VALUE IF NOT EXISTS 'contract_risk'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
