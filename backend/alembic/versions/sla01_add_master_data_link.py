"""Add master_data_id FK to contract_slas for library linking.

Revision ID: sla01_add_master_data_link
Revises: sso01_add_sso_oidc_enum
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "sla01_add_master_data_link"
down_revision = "sso01_add_sso_oidc_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contract_slas",
        sa.Column(
            "master_data_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sla_master_data.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_contract_slas_master_data", "contract_slas", ["master_data_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_slas_master_data", table_name="contract_slas")
    op.drop_column("contract_slas", "master_data_id")
