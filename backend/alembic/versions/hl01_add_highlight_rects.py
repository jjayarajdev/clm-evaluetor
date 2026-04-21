"""Add highlight_rects JSONB column to clauses, obligations, and contract_slas tables.

Revision ID: hl01_add_highlight_rects
Revises: sla01_add_master_data_link
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "hl01_add_highlight_rects"
down_revision = "sla01_add_master_data_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clauses", sa.Column("highlight_rects", JSONB(), nullable=True))
    op.add_column("obligations", sa.Column("highlight_rects", JSONB(), nullable=True))
    op.add_column("contract_slas", sa.Column("highlight_rects", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("contract_slas", "highlight_rects")
    op.drop_column("obligations", "highlight_rects")
    op.drop_column("clauses", "highlight_rects")
