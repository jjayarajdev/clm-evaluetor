"""Add tenant_id to compliance_gaps and regulatory_obligations.

These tables were isolated only via a join to contracts.tenant_id. Add an
explicit, indexed, non-null tenant_id (defense-in-depth), backfilled from the
owning contract.

Revision ID: cmp01_compliance_tenant
Revises: org02_drop_code_key
Create Date: 2026-07-24
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "cmp01_compliance_tenant"
down_revision = "org02_drop_code_key"
branch_labels = None
depends_on = None

_TABLES = ("compliance_gaps", "regulatory_obligations")


def upgrade() -> None:
    for tbl in _TABLES:
        # 1. Add nullable so existing rows don't violate the constraint.
        op.add_column(
            tbl,
            sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        )
        # 2. Backfill from the owning contract.
        op.execute(
            f"""
            UPDATE {tbl} x SET tenant_id = c.tenant_id
            FROM contracts c
            WHERE c.id = x.contract_id
            """
        )
        # 3. Index + FK + NOT NULL now that every row is populated.
        op.create_index(f"ix_{tbl}_tenant_id", tbl, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{tbl}_tenant_id_tenants",
            tbl,
            "tenants",
            ["tenant_id"],
            ["id"],
        )
        op.alter_column(tbl, "tenant_id", nullable=False)


def downgrade() -> None:
    for tbl in _TABLES:
        op.drop_constraint(f"fk_{tbl}_tenant_id_tenants", tbl, type_="foreignkey")
        op.drop_index(f"ix_{tbl}_tenant_id", table_name=tbl)
        op.drop_column(tbl, "tenant_id")
