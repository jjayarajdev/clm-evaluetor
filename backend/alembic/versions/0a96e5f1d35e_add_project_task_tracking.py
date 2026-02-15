"""Add project task tracking models

Revision ID: 0a96e5f1d35e
Revises: g7h8i9j0k1l2
Create Date: 2026-02-10 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0a96e5f1d35e'
down_revision: Union[str, Sequence[str], None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add project tracking tables."""
    # Create enums using raw SQL with IF NOT EXISTS logic
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE taskstatus AS ENUM ('not_started', 'in_progress', 'blocked', 'completed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE taskpriority AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create project_phases table using raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_phases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phase_number INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            estimated_days INTEGER DEFAULT 1 NOT NULL,
            status taskstatus DEFAULT 'not_started' NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create project_tasks table
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phase_id UUID NOT NULL REFERENCES project_phases(id) ON DELETE CASCADE,
            task_id VARCHAR(20) NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            status taskstatus DEFAULT 'not_started' NOT NULL,
            priority taskpriority DEFAULT 'medium' NOT NULL,
            dependencies VARCHAR(500),
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            notes TEXT,
            files_created TEXT,
            files_modified TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create project_notes table
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_notes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID REFERENCES project_tasks(id) ON DELETE SET NULL,
            category VARCHAR(50) NOT NULL,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_phases_number ON project_phases(phase_number);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_tasks_phase ON project_tasks(phase_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_tasks_status ON project_tasks(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_project_notes_task ON project_notes(task_id);")


def downgrade() -> None:
    """Remove project tracking tables."""
    op.execute("DROP INDEX IF EXISTS ix_project_notes_task;")
    op.execute("DROP INDEX IF EXISTS ix_project_tasks_status;")
    op.execute("DROP INDEX IF EXISTS ix_project_tasks_phase;")
    op.execute("DROP INDEX IF EXISTS ix_project_phases_number;")

    op.execute("DROP TABLE IF EXISTS project_notes;")
    op.execute("DROP TABLE IF EXISTS project_tasks;")
    op.execute("DROP TABLE IF EXISTS project_phases;")

    op.execute("DROP TYPE IF EXISTS taskpriority;")
    op.execute("DROP TYPE IF EXISTS taskstatus;")
