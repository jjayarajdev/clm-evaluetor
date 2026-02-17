"""Add multi-tenancy support

Revision ID: o8p9q0r1s2t3
Revises: n7o8p9q0r1s2
Create Date: 2026-02-17

This migration:
1. Creates the tenants table
2. Adds tenant_id to users table
3. Adds tenant_id to contracts table
4. Seeds 3 tenants: Acme (default), TechStart, LegalCo
5. Migrates existing data to Acme tenant
6. Adds SUPER_ADMIN role
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'o8p9q0r1s2t3'
down_revision: Union[str, None] = 'n7o8p9q0r1s2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Predefined tenant UUIDs for consistency
ACME_TENANT_ID = '10000000-0000-0000-0000-000000000001'
TECHSTART_TENANT_ID = '10000000-0000-0000-0000-000000000002'
LEGALCO_TENANT_ID = '10000000-0000-0000-0000-000000000003'


def upgrade() -> None:
    # 1. Create tenant plan enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tenantplan AS ENUM ('starter', 'professional', 'enterprise', 'strategic');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # 2. Create tenants table using raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id UUID PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL UNIQUE,
            contact_email VARCHAR(255),
            contact_name VARCHAR(255),
            plan tenantplan NOT NULL DEFAULT 'starter',
            contract_limit INTEGER,
            settings TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenants_slug ON tenants(slug)")

    # 3. Seed tenants
    op.execute(f"""
        INSERT INTO tenants (id, name, slug, plan, contact_email, is_active)
        VALUES
            ('{ACME_TENANT_ID}', 'Acme Corporation', 'acme', 'professional', 'admin@acme.com', true),
            ('{TECHSTART_TENANT_ID}', 'TechStart Inc', 'techstart', 'starter', 'admin@techstart.io', true),
            ('{LEGALCO_TENANT_ID}', 'LegalCo Partners', 'legalco', 'enterprise', 'admin@legalco.com', true)
        ON CONFLICT (slug) DO NOTHING
    """)

    # 4. Update role enum to add super_admin
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'super_admin'")

    # 5. Add full_name column to users if it doesn't exist
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN full_name VARCHAR(255);
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)

    # 6. Add tenant_id to users table (nullable initially for migration)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN tenant_id UUID REFERENCES tenants(id);
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users(tenant_id)")

    # 7. Assign existing users to Acme tenant
    op.execute(f"""
        UPDATE users SET tenant_id = '{ACME_TENANT_ID}' WHERE tenant_id IS NULL
    """)

    # 8. Add tenant_id to contracts table (nullable initially for migration)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE contracts ADD COLUMN tenant_id UUID;
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_contracts_tenant_id ON contracts(tenant_id)")

    # 9. Assign existing contracts to Acme tenant
    op.execute(f"""
        UPDATE contracts SET tenant_id = '{ACME_TENANT_ID}' WHERE tenant_id IS NULL
    """)

    # 10. Make tenant_id NOT NULL on contracts and add foreign key
    op.execute("ALTER TABLE contracts ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE contracts ADD CONSTRAINT fk_contracts_tenant_id
            FOREIGN KEY (tenant_id) REFERENCES tenants(id);
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # 11. Add tenant_id to clients
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE clients ADD COLUMN tenant_id UUID;
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute(f"UPDATE clients SET tenant_id = '{ACME_TENANT_ID}' WHERE tenant_id IS NULL")
    op.execute("ALTER TABLE clients ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE clients ADD CONSTRAINT fk_clients_tenant_id
            FOREIGN KEY (tenant_id) REFERENCES tenants(id);
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_clients_tenant_id ON clients(tenant_id)")

    # 12. Add tenant_id to organizations
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE organizations ADD COLUMN tenant_id UUID;
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute(f"UPDATE organizations SET tenant_id = '{ACME_TENANT_ID}' WHERE tenant_id IS NULL")
    op.execute("ALTER TABLE organizations ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE organizations ADD CONSTRAINT fk_organizations_tenant_id
            FOREIGN KEY (tenant_id) REFERENCES tenants(id);
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_organizations_tenant_id ON organizations(tenant_id)")

    # 13. Add tenant_id to business_relationships
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE business_relationships ADD COLUMN tenant_id UUID;
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute(f"UPDATE business_relationships SET tenant_id = '{ACME_TENANT_ID}' WHERE tenant_id IS NULL")
    op.execute("ALTER TABLE business_relationships ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE business_relationships ADD CONSTRAINT fk_business_relationships_tenant_id
            FOREIGN KEY (tenant_id) REFERENCES tenants(id);
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_business_relationships_tenant_id ON business_relationships(tenant_id)")


def downgrade() -> None:
    # Remove tenant_id from business_relationships
    op.execute("DROP INDEX IF EXISTS ix_business_relationships_tenant_id")
    op.execute("ALTER TABLE business_relationships DROP CONSTRAINT IF EXISTS fk_business_relationships_tenant_id")
    op.execute("ALTER TABLE business_relationships DROP COLUMN IF EXISTS tenant_id")

    # Remove tenant_id from organizations
    op.execute("DROP INDEX IF EXISTS ix_organizations_tenant_id")
    op.execute("ALTER TABLE organizations DROP CONSTRAINT IF EXISTS fk_organizations_tenant_id")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS tenant_id")

    # Remove tenant_id from clients
    op.execute("DROP INDEX IF EXISTS ix_clients_tenant_id")
    op.execute("ALTER TABLE clients DROP CONSTRAINT IF EXISTS fk_clients_tenant_id")
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS tenant_id")

    # Remove tenant_id from contracts
    op.execute("ALTER TABLE contracts DROP CONSTRAINT IF EXISTS fk_contracts_tenant_id")
    op.execute("DROP INDEX IF EXISTS ix_contracts_tenant_id")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS tenant_id")

    # Remove tenant_id and full_name from users
    op.execute("DROP INDEX IF EXISTS ix_users_tenant_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS tenant_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS full_name")

    # Drop tenants table
    op.execute("DROP INDEX IF EXISTS ix_tenants_slug")
    op.execute("DROP TABLE IF EXISTS tenants")

    # Drop tenantplan enum
    op.execute("DROP TYPE IF EXISTS tenantplan")
