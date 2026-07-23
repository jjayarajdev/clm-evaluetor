"""Add industry_profile_id to contracts table.

Allows each contract to have its own industry profile,
overriding the tenant/BU default. Resolution chain becomes:
Contract profile -> BU profile -> Tenant profile -> empty.

Revision ID: cp01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "cp01"
down_revision = "ct01_contract_type_to_varchar"  # after industry_profiles exists
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column(
            "industry_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("industry_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_contracts_industry_profile_id",
        "contracts",
        ["industry_profile_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contracts_industry_profile_id", table_name="contracts")
    op.drop_column("contracts", "industry_profile_id")
