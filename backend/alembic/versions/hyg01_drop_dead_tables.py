"""DB hygiene: drop four genuinely-dead tables.

All four are empty and have zero code usage (verified):
  - project_notes / project_tasks / project_phases  (project-tracking feature,
    never wired to any router/service; self-contained FK cluster)
  - alert_configs  (superseded by notification_rules; only prior reference was a
    tenant-purge DELETE, now removed)

Dormant-but-WIRED empties (clients, compliance_*, dashboard_cache,
sla_measurements, kg_*) are deliberately NOT dropped here — they're live code
paths, a feature decision rather than hygiene.

Revision ID: hyg01_drop_dead
Revises: link01_manual_child
Create Date: 2026-07-26
"""

from alembic import op


revision = "hyg01_drop_dead"
down_revision = "link01_manual_child"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop child-first to satisfy the self-referential FK cluster
    # (project_notes -> project_tasks -> project_phases).
    op.execute("DROP TABLE IF EXISTS project_notes CASCADE")
    op.execute("DROP TABLE IF EXISTS project_tasks CASCADE")
    op.execute("DROP TABLE IF EXISTS project_phases CASCADE")
    op.execute("DROP TABLE IF EXISTS alert_configs CASCADE")


def downgrade() -> None:
    # These tables were empty and unused; recreation is intentionally not
    # provided. Restore from the model history if ever needed.
    pass
