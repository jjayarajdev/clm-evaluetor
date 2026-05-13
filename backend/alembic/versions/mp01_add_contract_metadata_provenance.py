"""Add metadata_provenance JSONB to contracts.

Stores the source quote and confidence for each AI-extracted metadata field
(counterparty, contract_type, dates, contract_value, currency, jurisdiction).
The AI already returns a ``raw_text`` per field; this migration adds the
column so we can persist it for UI display ("where did this value come from?").

Shape:
    {
      "counterparty":    {"raw_text": "between Acme Inc. and Vialto", "confidence": 0.92},
      "contract_value":  {"raw_text": "total amount of $50,000",     "confidence": 0.88},
      ...
    }

Revision ID: mp01
Down revision: eh01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "mp01"
down_revision = "eh01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("metadata_provenance", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contracts", "metadata_provenance")
