"""Add extraction_health JSONB column to contracts table.

Tracks per-stage outcomes of the extraction pipeline (success/failed/skipped)
so tenants can see which optional stages succeeded/failed for a given contract,
instead of those failures being silent.

Shape:
    {
      "metadata":          {"status": "success", "duration_ms": 1234},
      "knowledge_graph":   {"status": "failed",  "error": "..."},
      "schema_extraction": {"status": "skipped", "reason": "no schema for contract_type=NDA"},
      ...
    }

Revision ID: eh01
Down revision: cp01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "eh01"
down_revision = "cp01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column(
            "extraction_health",
            JSONB,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("contracts", "extraction_health")
