"""Add IT service contract clause types

Revision ID: h1i2j3k4l5m6
Revises: 92b4d0a15c40
Create Date: 2026-02-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, Sequence[str], None] = '92b4d0a15c40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add IT service/outsourcing clause types to clausetype enum."""
    # Add new enum values for IT service contracts
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'service_description'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'service_level'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'deliverable'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'governance'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'transition'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'change_management'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'support'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'security'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'personnel'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'pricing'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'risk_mitigation'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'scope'")
    op.execute("ALTER TYPE clausetype ADD VALUE IF NOT EXISTS 'acceptance'")


def downgrade() -> None:
    """Downgrade - PostgreSQL doesn't easily support removing enum values."""
    # Note: PostgreSQL doesn't support removing enum values easily
    # The new clause type enum values will remain
    pass
