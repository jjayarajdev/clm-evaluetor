"""Add missing obligation columns

Revision ID: s2t3u4v5w6x7
Revises: r1s2t3u4v5w6
Create Date: 2026-02-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 's2t3u4v5w6x7'
down_revision: Union[str, None] = 'r1s2t3u4v5w6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_text column to obligations if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'obligations' AND column_name = 'source_text'
            ) THEN
                ALTER TABLE obligations ADD COLUMN source_text TEXT;
            END IF;
        END $$;
    """)

    # Add extra_data column to sla_alerts (model uses extra_data, migration created metadata)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'sla_alerts' AND column_name = 'extra_data'
            ) THEN
                ALTER TABLE sla_alerts ADD COLUMN extra_data JSONB;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_column('obligations', 'source_text')
