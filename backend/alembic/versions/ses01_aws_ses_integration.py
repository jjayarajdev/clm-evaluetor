"""Add AWS SES integration system and external user recipient type

Revision ID: ses01_aws_ses
Revises: fg06_processingjobs, aa01_is_demo
Create Date: 2026-04-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ses01_aws_ses'
down_revision: Union[str, Sequence[str], None] = ('fg06_processingjobs', 'aa01_is_demo')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add aws_ses to IntegrationSystem enum
    op.execute("ALTER TYPE integrationsystem ADD VALUE IF NOT EXISTS 'aws_ses'")

    # Add external_user to RecipientType enum for external portal notifications
    op.execute("ALTER TYPE recipienttype ADD VALUE IF NOT EXISTS 'external_user'")


def downgrade() -> None:
    # PostgreSQL enums cannot have values removed; no-op
    pass
