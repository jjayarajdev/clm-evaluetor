"""Add industry_profiles table and link to tenants.

Revision ID: ip01_add_industry_profiles
Revises: hl01_add_highlight_rects
Create Date: 2026-04-22 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "ip01_add_industry_profiles"
down_revision: Union[str, None] = "hl01_add_highlight_rects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create industry_profiles table
    op.create_table(
        "industry_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contract_types", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("clause_types", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("risk_categories", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("sla_metrics", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("field_definitions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("extraction_hints", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ui_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_industry_profiles_slug", "industry_profiles", ["slug"])

    # Add industry_profile_id and config_overrides to tenants
    op.add_column(
        "tenants",
        sa.Column(
            "industry_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("industry_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "config_overrides",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_tenants_industry_profile_id", "tenants", ["industry_profile_id"])


def downgrade() -> None:
    op.drop_index("ix_tenants_industry_profile_id", "tenants")
    op.drop_column("tenants", "config_overrides")
    op.drop_column("tenants", "industry_profile_id")
    op.drop_index("ix_industry_profiles_slug", "industry_profiles")
    op.drop_table("industry_profiles")
