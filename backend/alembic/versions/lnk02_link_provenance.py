"""Add link provenance for evidence-ranked arbitration.

contract_links.created_by_rule records which detection rule made a link
(NULL = human). Existing machine links are backfilled from their
description prefixes; unknown descriptions stay NULL (treated as human —
conservative: the referee will never replace them).

Revision ID: lnk02_link_provenance
Revises: grp01_contract_groups is already ancestor; parent = lnk01
"""

import sqlalchemy as sa
from alembic import op

revision = "lnk02_link_provenance"
down_revision = "lnk01_fix_linktype"
branch_labels = None
depends_on = None

_BACKFILL = [
    ("Declared reference%", "declared_reference"),
    ("Work package structure%", "document_number"),
    ("Framework set%", "framework_set"),
    ("Counterparty family%", "counterparty_master"),
    ("Auto-detected%", "llm_detection"),
    ("Auto-approved%", "llm_detection"),
]


def upgrade() -> None:
    op.add_column(
        "contract_links",
        sa.Column("created_by_rule", sa.String(50), nullable=True),
    )
    for pattern, rule in _BACKFILL:
        op.execute(
            sa.text(
                "UPDATE contract_links SET created_by_rule = :rule "
                "WHERE link_description LIKE :pattern AND created_by_rule IS NULL"
            ).bindparams(rule=rule, pattern=pattern)
        )


def downgrade() -> None:
    op.drop_column("contract_links", "created_by_rule")
