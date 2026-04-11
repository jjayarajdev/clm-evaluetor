"""Add is_demo flag to integration_configs.

Revision ID: aa01_is_demo
Revises: y8z9a0b1c2d3
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa


revision = "aa01_is_demo"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "integration_configs",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Mark existing provisioned configs as demo
    op.execute(
        "UPDATE integration_configs SET is_demo = true "
        "WHERE credentials::text LIKE '%configured%' OR credentials::text LIKE '%demo%'"
    )


def downgrade() -> None:
    op.drop_column("integration_configs", "is_demo")
