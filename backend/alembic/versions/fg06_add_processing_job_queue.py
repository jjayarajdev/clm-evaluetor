"""Add contract processing job queue for reliable batch processing

Revision ID: fg06_processingjobs
Revises: fg05_snowslasync
Create Date: 2026-03-29 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "fg06_processingjobs"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the processing job status enum
    op.execute(
        "CREATE TYPE processingjobstatus AS ENUM "
        "('queued', 'processing', 'completed', 'failed', 'stuck')"
    )

    # Create the processing jobs table
    op.create_table(
        "contract_processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("batch_id", sa.String(64), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued", "processing", "completed", "failed", "stuck",
                name="processingjobstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("stage", sa.String(50), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes
    op.create_index(
        "ix_processing_jobs_contract_id",
        "contract_processing_jobs",
        ["contract_id"],
    )
    op.create_index(
        "ix_processing_jobs_tenant_id",
        "contract_processing_jobs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_processing_jobs_batch_id",
        "contract_processing_jobs",
        ["batch_id"],
    )
    op.create_index(
        "ix_processing_jobs_queue",
        "contract_processing_jobs",
        ["status", "priority", "created_at"],
    )
    op.create_index(
        "ix_processing_jobs_batch_status",
        "contract_processing_jobs",
        ["batch_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("contract_processing_jobs")
    op.execute("DROP TYPE IF EXISTS processingjobstatus")
