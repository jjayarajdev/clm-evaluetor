"""Sync missing enum values between Python and PostgreSQL

Revision ID: u4v5w6x7y8z9
Revises: t3u4v5w6x7y8
Create Date: 2026-02-22 16:30:00.000000

This migration adds enum values that exist in Python models but were
missing from the PostgreSQL database enums. This ensures local dev
(which may auto-create enums) and Docker/production (which uses
migrations) have identical enum values.

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'u4v5w6x7y8z9'
down_revision: Union[str, None] = 't3u4v5w6x7y8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Role enum - add super_admin (used by superadmin user)
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'super_admin'")

    # 2. AuditAction enum - add contract_update
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'contract_update'")

    # 3. PartyRole enum - create if not exists (was completely missing)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'partyrole') THEN
                CREATE TYPE partyrole AS ENUM (
                    'provider',
                    'client',
                    'vendor',
                    'customer',
                    'licensor',
                    'licensee',
                    'employer',
                    'employee',
                    'disclosing_party',
                    'receiving_party',
                    'other'
                );
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # PostgreSQL doesn't easily support removing enum values
    # PartyRole type would need to be dropped if no tables use it
    pass
