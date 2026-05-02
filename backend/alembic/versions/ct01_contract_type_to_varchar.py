"""Convert contract_type from PostgreSQL enum to VARCHAR for multi-domain support.

Revision ID: ct01_contract_type_to_varchar
Revises: ip01_add_industry_profiles
Create Date: 2026-04-22 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "ct01_contract_type_to_varchar"
down_revision: Union[str, None] = "ip01_add_industry_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Convert contracts.contract_type from enum to varchar
    # Must use raw SQL because Alembic's alter_column doesn't handle enum→varchar well
    op.execute("""
        ALTER TABLE contracts
        ALTER COLUMN contract_type TYPE VARCHAR(100)
        USING contract_type::text
    """)

    # Step 2: Convert industry_compliance_rules.primary_contract_type from enum to varchar
    op.execute("""
        ALTER TABLE industry_compliance_rules
        ALTER COLUMN primary_contract_type TYPE VARCHAR(100)
        USING primary_contract_type::text
    """)

    # Step 3: Drop the PostgreSQL enum type (no longer needed)
    op.execute("DROP TYPE IF EXISTS contracttype")


def downgrade() -> None:
    # Recreate the enum type
    op.execute("""
        CREATE TYPE contracttype AS ENUM (
            'nda', 'msa', 'sow', 'amendment', 'vendor_agreement', 'employment_contract'
        )
    """)

    # Convert back to enum
    op.execute("""
        ALTER TABLE contracts
        ALTER COLUMN contract_type TYPE contracttype
        USING contract_type::contracttype
    """)
    op.execute("""
        ALTER TABLE industry_compliance_rules
        ALTER COLUMN primary_contract_type TYPE contracttype
        USING primary_contract_type::contracttype
    """)
