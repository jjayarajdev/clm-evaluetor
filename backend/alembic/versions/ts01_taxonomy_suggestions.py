"""Add taxonomy_suggestions table.

Revision ID: ts01_taxonomy_suggestions
Revises: mp01
Create Date: 2026-04-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
# NOTE: renamed from "a1b2c3d4e5f6" which collided with
# a1b2c3d4e5f6_add_canonical_contract_tables.py
revision = "ts01_taxonomy_suggestions"
down_revision = "mp01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("source_agent", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, default=0.0),
        sa.Column("source_text", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="pending", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("taxonomy_suggestions")
