"""Add preferred_language to users.

Revision ID: lang01_user_language
Revises: b2c3d4e5f6g7
Create Date: 2026-07-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "lang01_user_language"
down_revision = "b2c3d4e5f6g7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_language", sa.String(5), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_language")
