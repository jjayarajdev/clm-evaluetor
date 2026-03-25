"""Add KPI approval workflow and relationship performance status history

Revision ID: fg04_kpiapproval
Revises: fg03_contractdocs
Create Date: 2026-03-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fg04_kpiapproval'
down_revision: Union[str, None] = 'fg03_contractdocs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Feature 1: KPI Evaluation Approval Workflow ===

    # Create score_approval_status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE scoreapprovalstatus AS ENUM ('draft', 'pending_approval', 'approved', 'rejected');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Add approval columns to perception_scores table
    op.add_column('perception_scores', sa.Column(
        'approval_status',
        postgresql.ENUM('draft', 'pending_approval', 'approved', 'rejected', name='scoreapprovalstatus', create_type=False),
        nullable=False,
        server_default='pending_approval',
    ))
    op.add_column('perception_scores', sa.Column(
        'approved_by',
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey('users.id'),
        nullable=True,
    ))
    op.add_column('perception_scores', sa.Column(
        'approved_at',
        sa.DateTime(),
        nullable=True,
    ))
    op.add_column('perception_scores', sa.Column(
        'approval_comments',
        sa.Text(),
        nullable=True,
    ))

    # Create index on approval_status for fast pending lookups
    op.create_index('ix_perception_scores_approval_status', 'perception_scores', ['approval_status'])

    # === Feature 2: Relationship Performance Status History ===

    # Create performance_status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE performancestatus AS ENUM ('excellent', 'good', 'acceptable', 'concerning', 'poor', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create relationship_status_history table
    op.create_table(
        'relationship_status_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_relationships.id'), nullable=False),
        sa.Column('status', postgresql.ENUM('excellent', 'good', 'acceptable', 'concerning', 'poor', 'critical', name='performancestatus', create_type=False), nullable=False),
        sa.Column('previous_status', postgresql.ENUM('excellent', 'good', 'acceptable', 'concerning', 'poor', 'critical', name='performancestatus', create_type=False), nullable=True),
        sa.Column('overall_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('recorded_date', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('recorded_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('trigger', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for common query patterns
    op.create_index('ix_relationship_status_history_tenant', 'relationship_status_history', ['tenant_id'])
    op.create_index('ix_relationship_status_history_relationship', 'relationship_status_history', ['relationship_id'])
    op.create_index('ix_relationship_status_history_period', 'relationship_status_history', ['period'])


def downgrade() -> None:
    # Drop relationship_status_history table and indexes
    op.drop_index('ix_relationship_status_history_period', table_name='relationship_status_history')
    op.drop_index('ix_relationship_status_history_relationship', table_name='relationship_status_history')
    op.drop_index('ix_relationship_status_history_tenant', table_name='relationship_status_history')
    op.drop_table('relationship_status_history')

    # Drop performance_status enum
    op.execute("DROP TYPE IF EXISTS performancestatus")

    # Drop approval columns from perception_scores
    op.drop_index('ix_perception_scores_approval_status', table_name='perception_scores')
    op.drop_column('perception_scores', 'approval_comments')
    op.drop_column('perception_scores', 'approved_at')
    op.drop_column('perception_scores', 'approved_by')
    op.drop_column('perception_scores', 'approval_status')

    # Drop score_approval_status enum
    op.execute("DROP TYPE IF EXISTS scoreapprovalstatus")
