"""Add contract grouping tables.

contract_groups (manual / upload_batch / auto_family, nestable, ownable),
contract_group_members (with provenance), contract_group_findings
(missing-reference findings, populated in grouping Phase 2).

Revision ID: grp01_contract_groups
Revises: evt01_fix_eventtype
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "grp01_contract_groups"
down_revision = "evt01_fix_eventtype"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("group_type", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("parent_group_id", UUID(as_uuid=True), sa.ForeignKey("contract_groups.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("root_contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("upload_batch_id", sa.String(100), nullable=True, index=True),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_contract_groups_auto_root",
        "contract_groups",
        ["tenant_id", "root_contract_id"],
        unique=True,
        postgresql_where=sa.text("group_type = 'auto_family'"),
    )
    op.create_index(
        "uq_contract_groups_batch",
        "contract_groups",
        ["tenant_id", "upload_batch_id"],
        unique=True,
        postgresql_where=sa.text("group_type = 'upload_batch'"),
    )

    op.create_table(
        "contract_group_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("contract_groups.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("added_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("group_id", "contract_id", name="uq_group_member"),
    )

    op.create_table(
        "contract_group_findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey("contract_groups.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("finding_type", sa.String(50), nullable=False, server_default="missing_reference"),
        sa.Column("reference_label", sa.String(255), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolved_by_contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dismissed_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "contract_id", "reference_label", name="uq_group_finding_reference"),
    )
    op.create_index(
        "ix_group_findings_status", "contract_group_findings", ["group_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("contract_group_findings")
    op.drop_table("contract_group_members")
    op.drop_table("contract_groups")
