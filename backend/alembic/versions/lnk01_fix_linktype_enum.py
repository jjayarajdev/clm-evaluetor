"""Add missing LinkType values to the linktype enum.

Databases bootstrapped via create_all with an older model carry a legacy
linktype enum (parent, child, referenced, ...) missing the 16 values the
current ContractLink model uses — link creation then fails with
InvalidTextRepresentationError. Adds the model's values idempotently
(same drift class as evt01_fix_eventtype).

Revision ID: lnk01_fix_linktype
Revises: grp01_contract_groups
Create Date: 2026-07-23
"""

from alembic import op

revision = "lnk01_fix_linktype"
down_revision = "grp01_contract_groups"
branch_labels = None
depends_on = None

LINK_TYPE_VALUES = [
    "sow", "work_order", "service_order", "purchase_order",
    "amendment", "addendum", "change_order", "modification", "renewal",
    "exhibit", "schedule", "appendix", "attachment",
    "supersedes", "references", "related",
]


def upgrade() -> None:
    for value in LINK_TYPE_VALUES:
        op.execute(f"ALTER TYPE linktype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values; no-op.
    pass
