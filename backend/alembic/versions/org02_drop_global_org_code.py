"""Drop the global unique on organizations.code (tenant-scope it).

Org codes are meant to be unique *per tenant* (the model already declares
uq_org_tenant_code), but prod still carried the legacy global
organizations_code_key constraint. That let the governance bridge's
per-tenant uniqueness check pass while the global constraint rejected a code
already used by another tenant. Drop the global constraint and ensure the
composite one exists.

Revision ID: org02_drop_code_key
Revises: org01_contract_org
Create Date: 2026-07-24
"""
from alembic import op

revision = "org02_drop_code_key"
down_revision = "org01_contract_org"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the legacy global unique constraint if present.
    op.execute("ALTER TABLE organizations DROP CONSTRAINT IF EXISTS organizations_code_key")
    # Ensure the tenant-scoped composite unique exists (idempotent).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_org_tenant_code'
            ) THEN
                ALTER TABLE organizations
                    ADD CONSTRAINT uq_org_tenant_code UNIQUE (tenant_id, code);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Non-reversible in a safe way (re-adding a global unique could fail on
    # existing cross-tenant duplicates); leave the tenant-scoped constraint.
    pass
