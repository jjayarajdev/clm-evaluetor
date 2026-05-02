"""Add industry_profile_id and config_overrides to business_units, business_unit_id to taxonomy_suggestions.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-23 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision = "b2c3d4e5f6g7"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add industry profile support to business_units
    op.add_column(
        "business_units",
        sa.Column(
            "industry_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("industry_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "business_units",
        sa.Column(
            "config_overrides",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index(
        "ix_business_units_industry_profile_id",
        "business_units",
        ["industry_profile_id"],
    )

    # Add business_unit_id to taxonomy_suggestions
    op.add_column(
        "taxonomy_suggestions",
        sa.Column(
            "business_unit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("business_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_taxonomy_suggestions_business_unit_id",
        "taxonomy_suggestions",
        ["business_unit_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_taxonomy_suggestions_business_unit_id", "taxonomy_suggestions")
    op.drop_column("taxonomy_suggestions", "business_unit_id")
    op.drop_index("ix_business_units_industry_profile_id", "business_units")
    op.drop_column("business_units", "config_overrides")
    op.drop_column("business_units", "industry_profile_id")
