"""Add a generic 'child' link type for manual drag-to-parent moves.

The tree/family logic treats 'related' and 'references' as lateral (non-nesting)
links, but the drag-to-move UI was creating 'related' links — so moved contracts
never nested under their new parent. Manual moves now use 'child', a real
hierarchical type. This migration adds the enum value.

Revision ID: link01_manual_child
Revises: usr01_user_profile
Create Date: 2026-07-26
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "link01_manual_child"
down_revision = "usr01_user_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL 12+ allows ADD VALUE inside a transaction (the value just can't
    # be *used* in the same tx — we don't). Matches the project's enum convention.
    op.execute("ALTER TYPE linktype ADD VALUE IF NOT EXISTS 'child'")


def downgrade() -> None:
    # PostgreSQL cannot drop a value from an enum type; leave it in place.
    pass
