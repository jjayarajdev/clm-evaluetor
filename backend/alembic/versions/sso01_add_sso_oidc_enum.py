"""Add sso_oidc to IntegrationSystem enum.

Revision ID: sso01_add_sso_oidc_enum
Revises: sp01_add_sharepoint_enum
Create Date: 2026-04-16
"""

from alembic import op

# revision identifiers
revision = "sso01_add_sso_oidc_enum"
down_revision = "sp01_add_sharepoint_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE integrationsystem ADD VALUE IF NOT EXISTS 'sso_oidc'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values
    pass
