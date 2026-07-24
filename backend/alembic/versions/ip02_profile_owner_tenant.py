"""Add owner_tenant_id to industry_profiles for tenant isolation.

Profiles were global — a tenant-created profile leaked into every tenant's
admin page and profile matching. owner_tenant_id: NULL = global/system,
else the owning tenant. Backfill: non-system profiles used as the default by
exactly one tenant are assigned to that tenant; system slugs and shared
profiles stay global.

Revision ID: ip02_profile_owner_tenant
Revises: lnk02_link_provenance
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "ip02_profile_owner_tenant"
down_revision = "lnk02_link_provenance"
branch_labels = None
depends_on = None

# Seeded, shared-across-tenants profiles — always global
_SYSTEM_SLUGS = (
    "it-services", "legal", "manufacturing", "pharma", "logistics",
)


def upgrade() -> None:
    op.add_column(
        "industry_profiles",
        sa.Column(
            "owner_tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_industry_profiles_owner_tenant_id",
        "industry_profiles",
        ["owner_tenant_id"],
    )
    # Assign non-system profiles to the single tenant that defaults to them
    op.execute(
        sa.text(
            """
            UPDATE industry_profiles p
            SET owner_tenant_id = t.tenant_id
            FROM (
                SELECT industry_profile_id,
                       (array_agg(id))[1] AS tenant_id,
                       COUNT(*) AS n
                FROM tenants
                WHERE industry_profile_id IS NOT NULL
                GROUP BY industry_profile_id
                HAVING COUNT(*) = 1
            ) t
            WHERE p.id = t.industry_profile_id
              AND p.slug NOT IN :system_slugs
            """
        ).bindparams(sa.bindparam("system_slugs", _SYSTEM_SLUGS, expanding=True))
    )


def downgrade() -> None:
    op.drop_index("ix_industry_profiles_owner_tenant_id", "industry_profiles")
    op.drop_column("industry_profiles", "owner_tenant_id")
