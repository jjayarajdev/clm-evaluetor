"""Add contracts.organization_id (canonical counterparty org).

Single source of truth so the Organizations registry and the Vendors view
are provably the same set. Backfill matches each contract's stored
counterparty to its tenant's organization by canonical org key.

Revision ID: org01_contract_org
Revises: iso01_tenant_scope
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "org01_contract_org"
down_revision = "iso01_tenant_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_contracts_organization_id", "contracts", ["organization_id"])
    # Exact-name backfill for the common case; canonical-key backfill for
    # variants runs from application code (needs the resolver).
    op.execute(
        """
        UPDATE contracts c SET organization_id = o.id
        FROM organizations o
        WHERE o.tenant_id = c.tenant_id
          AND lower(o.name) = lower(c.counterparty)
          AND c.counterparty IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_contracts_organization_id", "contracts")
    op.drop_column("contracts", "organization_id")
