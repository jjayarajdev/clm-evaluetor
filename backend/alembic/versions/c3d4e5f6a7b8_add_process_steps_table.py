"""Add contract_process_steps table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-01 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enums (IF NOT EXISTS for idempotency)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE steptype AS ENUM ('submission', 'review', 'testing', 'approval', 'delivery', 'certification', 'payment', 'reporting', 'renewal', 'other');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE stepstatus AS ENUM ('pending', 'in_progress', 'completed', 'blocked');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create contract_process_steps table using raw SQL to avoid enum creation issues
    op.execute("""
        CREATE TABLE contract_process_steps (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            source_clause_id UUID REFERENCES clauses(id) ON DELETE SET NULL,
            step_number INTEGER NOT NULL,
            step_name VARCHAR(255) NOT NULL,
            step_type steptype NOT NULL,
            description TEXT,
            responsible_party VARCHAR(255),
            duration_days INTEGER,
            sla_days INTEGER,
            dependencies TEXT,
            deliverables TEXT,
            status stepstatus NOT NULL DEFAULT 'pending',
            source_text TEXT,
            section_reference VARCHAR(50),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)

    # Create indexes
    op.create_index('ix_process_steps_contract', 'contract_process_steps', ['contract_id'])
    op.create_index('ix_process_steps_type', 'contract_process_steps', ['step_type'])
    op.create_index('ix_process_steps_status', 'contract_process_steps', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_process_steps_status', table_name='contract_process_steps')
    op.drop_index('ix_process_steps_type', table_name='contract_process_steps')
    op.drop_index('ix_process_steps_contract', table_name='contract_process_steps')
    op.drop_table('contract_process_steps')
    op.execute("DROP TYPE IF EXISTS stepstatus")
    op.execute("DROP TYPE IF EXISTS steptype")
