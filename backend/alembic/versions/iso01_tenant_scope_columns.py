"""Add tenant_id to isolation-gap tables and backfill.

Isolation audit found four tenant-scoped tables with no tenant_id column,
letting monitor/survey/audit endpoints cross tenants. Adds tenant_id
(nullable, indexed) and backfills each from its natural owner:

- events            <- contracts.tenant_id (via contract_id)
- approval_requests <- events.tenant_id (via action_executions.event_id)
- survey_templates  <- business_relationships.tenant_id (via any instance)
- audit_logs        <- users.tenant_id (via user_id)

Revision ID: iso01_tenant_scope
Revises: ip02_profile_owner_tenant
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "iso01_tenant_scope"
down_revision = "ip02_profile_owner_tenant"
branch_labels = None
depends_on = None


def _add_tenant_col(table: str) -> None:
    op.add_column(
        table,
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def upgrade() -> None:
    _add_tenant_col("events")
    _add_tenant_col("approval_requests")
    _add_tenant_col("survey_templates")
    _add_tenant_col("audit_logs")

    # events <- contract
    op.execute(
        """
        UPDATE events e SET tenant_id = c.tenant_id
        FROM contracts c WHERE e.contract_id = c.id
        """
    )
    # approval_requests <- event (via action_execution)
    op.execute(
        """
        UPDATE approval_requests ar SET tenant_id = e.tenant_id
        FROM action_executions ax
        JOIN events e ON e.id = ax.event_id
        WHERE ar.action_execution_id = ax.id
        """
    )
    # survey_templates <- business_relationship of any instance
    op.execute(
        """
        UPDATE survey_templates st SET tenant_id = sub.tenant_id
        FROM (
            SELECT si.template_id, (array_agg(br.tenant_id))[1] AS tenant_id
            FROM survey_instances si
            JOIN business_relationships br ON br.id = si.relationship_id
            GROUP BY si.template_id
        ) sub
        WHERE st.id = sub.template_id
        """
    )
    # audit_logs <- acting user
    op.execute(
        """
        UPDATE audit_logs al SET tenant_id = u.tenant_id
        FROM users u WHERE al.user_id = u.id
        """
    )


def downgrade() -> None:
    for table in ("events", "approval_requests", "survey_templates", "audit_logs"):
        op.drop_index(f"ix_{table}_tenant_id", table)
        op.drop_column(table, "tenant_id")
