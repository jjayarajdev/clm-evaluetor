"""Add structured name + contact profile fields to users.

Adds first_name, last_name, job_title, phone, department. Backfills first/last
from the existing free-text full_name (first token -> first_name, remainder ->
last_name) so existing users keep a structured name.

Revision ID: usr01_user_profile
Revises: cmp01_compliance_tenant
Create Date: 2026-07-26
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "usr01_user_profile"
down_revision = "cmp01_compliance_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(length=128), nullable=True))

    # Backfill first/last from full_name: first word -> first_name, rest -> last_name.
    op.execute(
        """
        UPDATE users
        SET first_name = split_part(trim(full_name), ' ', 1),
            last_name = CASE
                WHEN position(' ' in trim(full_name)) > 0
                THEN NULLIF(trim(substring(trim(full_name)
                     from position(' ' in trim(full_name)) + 1)), '')
                ELSE NULL
            END
        WHERE full_name IS NOT NULL AND trim(full_name) <> '' AND first_name IS NULL
        """
    )


def downgrade() -> None:
    for col in ("department", "phone", "job_title", "last_name", "first_name"):
        op.drop_column("users", col)
