"""Make golden_set_contracts.tenant_id nullable for global/platform entries.

Revision ID: eq02_global_golden_set
Revises: eq01_extraction_quality
Create Date: 2026-04-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "eq02_global_golden_set"
down_revision: str = "eq01_extraction_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Make tenant_id nullable for global golden set entries
    op.alter_column(
        "golden_set_contracts",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=True,
    )

    # 2. Add is_global column
    op.add_column(
        "golden_set_contracts",
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 3. Drop old unique index and create new one
    # The old index (tenant_id, contract_id) won't work with NULLs
    # PostgreSQL treats NULLs as distinct in unique indexes, so we need
    # a partial unique index for global entries
    op.drop_index("ix_golden_set_tenant_contract", table_name="golden_set_contracts")

    # Unique per tenant+contract (for tenant-specific entries)
    op.create_index(
        "ix_golden_set_tenant_contract",
        "golden_set_contracts",
        ["tenant_id", "contract_id"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )

    # Unique per contract for global entries (one global entry per contract)
    op.create_index(
        "ix_golden_set_global_contract",
        "golden_set_contracts",
        ["contract_id"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )


def downgrade() -> None:
    # Drop partial indexes
    op.drop_index("ix_golden_set_global_contract", table_name="golden_set_contracts")
    op.drop_index("ix_golden_set_tenant_contract", table_name="golden_set_contracts")

    # Delete global entries before making NOT NULL
    op.execute("DELETE FROM golden_set_contracts WHERE tenant_id IS NULL")

    # Restore original unique index
    op.create_index(
        "ix_golden_set_tenant_contract",
        "golden_set_contracts",
        ["tenant_id", "contract_id"],
        unique=True,
    )

    # Drop is_global column
    op.drop_column("golden_set_contracts", "is_global")

    # Make tenant_id NOT NULL again
    op.alter_column(
        "golden_set_contracts",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
