"""Add assigned_user_id to obligations (assignee for the review workflow).

Revision ID: oblassign01
Revises: hyg01_drop_dead
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "oblassign01"
down_revision = "hyg01_drop_dead"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "obligations",
        sa.Column("assigned_user_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_obligations_assigned_user",
        "obligations",
        "users",
        ["assigned_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_obligations_assigned_user_id",
        "obligations",
        ["assigned_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_obligations_assigned_user_id", table_name="obligations")
    op.drop_constraint("fk_obligations_assigned_user", "obligations", type_="foreignkey")
    op.drop_column("obligations", "assigned_user_id")
