"""Add new SLA metric types for IT service management

Revision ID: w6x7y8z9a0b1
Revises: v5w6x7y8z9a0
Create Date: 2024-02-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'w6x7y8z9a0b1'
down_revision: str | None = 'v5w6x7y8z9a0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add new SLA metric type enum values for comprehensive IT SLA coverage."""
    # Add new enum values to slametrictype
    # These cover common IT service management metrics that were falling back to 'custom'
    op.execute("ALTER TYPE slametrictype ADD VALUE IF NOT EXISTS 'success_rate'")
    op.execute("ALTER TYPE slametrictype ADD VALUE IF NOT EXISTS 'compliance_rate'")
    op.execute("ALTER TYPE slametrictype ADD VALUE IF NOT EXISTS 'utilization'")
    op.execute("ALTER TYPE slametrictype ADD VALUE IF NOT EXISTS 'recovery_time'")
    op.execute("ALTER TYPE slametrictype ADD VALUE IF NOT EXISTS 'recovery_point'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values
    # Would need to recreate the type and migrate data
    pass
