"""Add missing workflow event values to eventtype enum.

The workflow migration (b1c2d3e4f5g6) creates eventtype with
`EXCEPTION WHEN duplicate_object THEN null` — on databases where an older
eventtype enum (audit-action values) already existed, the workflow values
were silently never added, breaking /monitor/stats and event creation.

Revision ID: evt01_fix_eventtype
Revises: lang01_user_language
Create Date: 2026-07-23
"""

from alembic import op

revision = "evt01_fix_eventtype"
down_revision = "lang01_user_language"
branch_labels = None
depends_on = None

WORKFLOW_EVENT_VALUES = [
    "sla_breach",
    "sla_warning",
    "milestone_approaching",
    "milestone_overdue",
    "renewal_approaching",
    "renewal_overdue",
    "obligation_due",
    "obligation_overdue",
    "contract_expiring",
    "contract_expired",
    "benchmark_window",
    "cola_adjustment",
    "custom",
]


def upgrade() -> None:
    for value in WORKFLOW_EVENT_VALUES:
        op.execute(f"ALTER TYPE eventtype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values; no-op.
    pass
