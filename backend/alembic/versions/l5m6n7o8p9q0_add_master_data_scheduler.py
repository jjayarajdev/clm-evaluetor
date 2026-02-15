"""add master data and scheduler tables

Revision ID: l5m6n7o8p9q0
Revises: k4l5m6n7o8p9
Create Date: 2025-01-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'l5m6n7o8p9q0'
down_revision: Union[str, None] = 'k4l5m6n7o8p9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types (if not exists for idempotency)
    op.execute("DO $$ BEGIN CREATE TYPE schedulerjobstatus AS ENUM ('success', 'failed', 'running', 'skipped'); EXCEPTION WHEN duplicate_object THEN null; END $$")

    # Create sla_master_data table
    op.create_table(
        'sla_master_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reference_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_value', sa.Numeric(10, 4), nullable=False),
        sa.Column('minimum_value', sa.Numeric(10, 4), nullable=True),
        sa.Column('typical_performance', sa.Numeric(10, 4), nullable=True),
        sa.Column('volatility', sa.Numeric(10, 4), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('service_tower', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_code', name='uq_sla_master_reference_code'),
    )
    op.create_index('ix_sla_master_data_reference_code', 'sla_master_data', ['reference_code'])
    op.create_index('ix_sla_master_data_category', 'sla_master_data', ['category'])
    op.create_index('ix_sla_master_data_service_tower', 'sla_master_data', ['service_tower'])
    op.create_index('ix_sla_master_data_is_active', 'sla_master_data', ['is_active'])

    # Create milestone_master_data table
    op.create_table(
        'milestone_master_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('milestone_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('baseline_days_from_start', sa.Integer(), nullable=False),
        sa.Column('dependencies', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('credit_at_risk', sa.Numeric(15, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('milestone_code', name='uq_milestone_master_code'),
    )
    op.create_index('ix_milestone_master_data_milestone_code', 'milestone_master_data', ['milestone_code'])
    op.create_index('ix_milestone_master_data_is_active', 'milestone_master_data', ['is_active'])

    # Create scheduler_jobs table
    op.create_table(
        'scheduler_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_name', sa.String(100), nullable=False),
        sa.Column('job_type', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('interval_seconds', sa.Integer(), nullable=False, server_default='900'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', postgresql.ENUM(
            'success', 'failed', 'running', 'skipped',
            name='schedulerjobstatus',
            create_type=False
        ), nullable=True),
        sa.Column('last_run_duration_ms', sa.Integer(), nullable=True),
        sa.Column('last_run_error', sa.Text(), nullable=True),
        sa.Column('total_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_runs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_name', name='uq_scheduler_job_name'),
    )
    op.create_index('ix_scheduler_jobs_job_name', 'scheduler_jobs', ['job_name'])
    op.create_index('ix_scheduler_jobs_job_type', 'scheduler_jobs', ['job_type'])
    op.create_index('ix_scheduler_jobs_is_enabled', 'scheduler_jobs', ['is_enabled'])
    op.create_index('ix_scheduler_jobs_next_run_at', 'scheduler_jobs', ['next_run_at'])

    # Create scheduler_job_history table for detailed run history
    op.create_table(
        'scheduler_job_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'success', 'failed', 'running', 'skipped',
            name='schedulerjobstatus',
            create_type=False
        ), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('items_processed', sa.Integer(), nullable=True),
        sa.Column('run_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['scheduler_jobs.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_scheduler_job_history_job_id', 'scheduler_job_history', ['job_id'])
    op.create_index('ix_scheduler_job_history_started_at', 'scheduler_job_history', ['started_at'])
    op.create_index('ix_scheduler_job_history_status', 'scheduler_job_history', ['status'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('scheduler_job_history')
    op.drop_table('scheduler_jobs')
    op.drop_table('milestone_master_data')
    op.drop_table('sla_master_data')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS schedulerjobstatus")
