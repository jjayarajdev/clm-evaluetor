"""Add custom fields support

Revision ID: p9q0r1s2t3u4
Revises: o8p9q0r1s2t3
Create Date: 2026-02-19

This migration adds:
1. custom_field_definitions JSONB column to tenants table
2. custom_fields JSONB column to contracts, obligations, clauses, clients tables
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'p9q0r1s2t3u4'
down_revision: Union[str, None] = 'o8p9q0r1s2t3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add custom_field_definitions to tenants table
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE tenants ADD COLUMN custom_field_definitions JSONB NOT NULL DEFAULT '{}';
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        COMMENT ON COLUMN tenants.custom_field_definitions IS
        'Schema: {entity_type: [{name, label, field_type, required, options, extraction_hints, ...}]}'
    """)

    # 2. Add custom_fields to contracts table
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE contracts ADD COLUMN custom_fields JSONB NOT NULL DEFAULT '{}';
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    # Create GIN index for efficient JSONB queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contracts_custom_fields
        ON contracts USING GIN (custom_fields)
    """)

    # 3. Add custom_fields to obligations table
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE obligations ADD COLUMN custom_fields JSONB NOT NULL DEFAULT '{}';
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_obligations_custom_fields
        ON obligations USING GIN (custom_fields)
    """)

    # 4. Add custom_fields to clauses table
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE clauses ADD COLUMN custom_fields JSONB NOT NULL DEFAULT '{}';
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_clauses_custom_fields
        ON clauses USING GIN (custom_fields)
    """)

    # 5. Add custom_fields to clients table
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE clients ADD COLUMN custom_fields JSONB NOT NULL DEFAULT '{}';
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_clients_custom_fields
        ON clients USING GIN (custom_fields)
    """)


def downgrade() -> None:
    # Remove custom_fields from clients
    op.execute("DROP INDEX IF EXISTS ix_clients_custom_fields")
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS custom_fields")

    # Remove custom_fields from clauses
    op.execute("DROP INDEX IF EXISTS ix_clauses_custom_fields")
    op.execute("ALTER TABLE clauses DROP COLUMN IF EXISTS custom_fields")

    # Remove custom_fields from obligations
    op.execute("DROP INDEX IF EXISTS ix_obligations_custom_fields")
    op.execute("ALTER TABLE obligations DROP COLUMN IF EXISTS custom_fields")

    # Remove custom_fields from contracts
    op.execute("DROP INDEX IF EXISTS ix_contracts_custom_fields")
    op.execute("ALTER TABLE contracts DROP COLUMN IF EXISTS custom_fields")

    # Remove custom_field_definitions from tenants
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS custom_field_definitions")
