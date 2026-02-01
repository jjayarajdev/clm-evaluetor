"""initial_schema

Revision ID: a94bb936193e
Revises:
Create Date: 2026-02-01 00:38:54.859012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = 'a94bb936193e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define enums - these will be created separately
role_enum = ENUM('admin', 'legal', 'procurement', 'viewer', name='role', create_type=False)
contracttype_enum = ENUM('nda', 'msa', 'sow', 'amendment', 'vendor_agreement', 'employment_contract', 'vendor', 'employment', 'license', 'lease', name='contracttype', create_type=False)
contractstatus_enum = ENUM('pending', 'processing', 'completed', 'failed', name='contractstatus', create_type=False)
risklevel_enum = ENUM('low', 'medium', 'high', 'critical', name='risklevel', create_type=False)
clausetype_enum = ENUM('indemnification', 'limitation_of_liability', 'termination', 'confidentiality', 'intellectual_property', 'payment_terms', 'warranty', 'force_majeure', 'non_compete', 'non_solicitation', 'data_protection', 'dispute_resolution', 'assignment', 'notice', 'governing_law', 'sla', 'auto_renewal', name='clausetype', create_type=False)
obligationtype_enum = ENUM('payment', 'delivery', 'reporting', 'compliance', 'notification', 'performance', 'renewal', 'other', name='obligationtype', create_type=False)
deadlinetype_enum = ENUM('fixed_date', 'recurring', 'relative', 'ongoing', name='deadlinetype', create_type=False)
obligationstatus_enum = ENUM('pending', 'in_progress', 'completed', 'overdue', 'waived', name='obligationstatus', create_type=False)
auditaction_enum = ENUM('login', 'logout', 'login_failed', 'user_create', 'user_update', 'user_delete', 'contract_upload', 'contract_view', 'contract_delete', 'contract_download', 'contract_process', 'query_execute', 'agent_invoke', 'settings_update', name='auditaction', create_type=False)
alerttype_enum = ENUM('contract_expiration', 'renewal_notice', 'obligation_due', 'high_risk_detected', 'processing_complete', 'processing_failed', name='alerttype', create_type=False)


def upgrade() -> None:
    """Create initial schema with all tables."""

    # Create enum types using raw SQL
    op.execute("CREATE TYPE role AS ENUM ('admin', 'legal', 'procurement', 'viewer')")
    op.execute("CREATE TYPE contracttype AS ENUM ('nda', 'msa', 'sow', 'amendment', 'vendor_agreement', 'employment_contract', 'vendor', 'employment', 'license', 'lease')")
    op.execute("CREATE TYPE contractstatus AS ENUM ('pending', 'processing', 'completed', 'failed')")
    op.execute("CREATE TYPE risklevel AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE clausetype AS ENUM ('indemnification', 'limitation_of_liability', 'termination', 'confidentiality', 'intellectual_property', 'payment_terms', 'warranty', 'force_majeure', 'non_compete', 'non_solicitation', 'data_protection', 'dispute_resolution', 'assignment', 'notice', 'governing_law', 'sla', 'auto_renewal')")
    op.execute("CREATE TYPE obligationtype AS ENUM ('payment', 'delivery', 'reporting', 'compliance', 'notification', 'performance', 'renewal', 'other')")
    op.execute("CREATE TYPE deadlinetype AS ENUM ('fixed_date', 'recurring', 'relative', 'ongoing')")
    op.execute("CREATE TYPE obligationstatus AS ENUM ('pending', 'in_progress', 'completed', 'overdue', 'waived')")
    op.execute("CREATE TYPE auditaction AS ENUM ('login', 'logout', 'login_failed', 'user_create', 'user_update', 'user_delete', 'contract_upload', 'contract_view', 'contract_delete', 'contract_download', 'contract_process', 'query_execute', 'agent_invoke', 'settings_update')")
    op.execute("CREATE TYPE alerttype AS ENUM ('contract_expiration', 'renewal_notice', 'obligation_due', 'high_risk_detected', 'processing_complete', 'processing_failed')")

    # Users table
    op.create_table(
        'users',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', role_enum, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Contracts table
    op.create_table(
        'contracts',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('contract_type', contracttype_enum, nullable=True),
        sa.Column('counterparty', sa.String(255), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('expiration_date', sa.Date(), nullable=True),
        sa.Column('contract_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('jurisdiction', sa.String(100), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('risk_level', risklevel_enum, nullable=True),
        sa.Column('auto_renewal', sa.Boolean(), nullable=True),
        sa.Column('notice_period_days', sa.Integer(), nullable=True),
        sa.Column('renewal_term_months', sa.Integer(), nullable=True),
        sa.Column('status', contractstatus_enum, nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('uploaded_by', UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
    )
    op.create_index('ix_contracts_contract_type', 'contracts', ['contract_type'])
    op.create_index('ix_contracts_counterparty', 'contracts', ['counterparty'])
    op.create_index('ix_contracts_expiration_date', 'contracts', ['expiration_date'])
    op.create_index('ix_contracts_risk_level', 'contracts', ['risk_level'])
    op.create_index('ix_contracts_status', 'contracts', ['status'])
    op.create_index('ix_contracts_expiration_risk', 'contracts', ['expiration_date', 'risk_level'])
    op.create_index('ix_contracts_type_status', 'contracts', ['contract_type', 'status'])

    # Clauses table
    op.create_table(
        'clauses',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('contract_id', UUID(), nullable=False),
        sa.Column('clause_type', clausetype_enum, nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('section_number', sa.String(50), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.Column('risk_level', risklevel_enum, nullable=True),
        sa.Column('risk_reason', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('extracted_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_clauses_contract_id', 'clauses', ['contract_id'])
    op.create_index('ix_clauses_clause_type', 'clauses', ['clause_type'])
    op.create_index('ix_clauses_risk_level', 'clauses', ['risk_level'])
    op.create_index('ix_clauses_contract_type', 'clauses', ['contract_id', 'clause_type'])
    op.create_index('ix_clauses_risk', 'clauses', ['risk_level', 'confidence_score'])

    # Obligations table
    op.create_table(
        'obligations',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('contract_id', UUID(), nullable=False),
        sa.Column('clause_id', UUID(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('obligation_type', obligationtype_enum, nullable=False, server_default='other'),
        sa.Column('obligated_party', sa.String(255), nullable=True),
        sa.Column('beneficiary_party', sa.String(255), nullable=True),
        sa.Column('deadline_type', deadlinetype_enum, nullable=True),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('recurrence_pattern', sa.String(100), nullable=True),
        sa.Column('relative_deadline_text', sa.String(255), nullable=True),
        sa.Column('status', obligationstatus_enum, nullable=False, server_default='pending'),
        sa.Column('consequence_of_breach', sa.Text(), nullable=True),
        sa.Column('trigger_condition', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clause_id'], ['clauses.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_obligations_contract_id', 'obligations', ['contract_id'])
    op.create_index('ix_obligations_obligation_type', 'obligations', ['obligation_type'])
    op.create_index('ix_obligations_deadline', 'obligations', ['deadline'])
    op.create_index('ix_obligations_status', 'obligations', ['status'])
    op.create_index('ix_obligations_contract_status', 'obligations', ['contract_id', 'status'])
    op.create_index('ix_obligations_deadline_status', 'obligations', ['deadline', 'status'])

    # Audit logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=True),
        sa.Column('action', auditaction_enum, nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(50), nullable=True),
        sa.Column('details', JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_user_action_time', 'audit_logs', ['user_id', 'action', 'created_at'])

    # Alert configs table
    op.create_table(
        'alert_configs',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('alert_type', alerttype_enum, nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('threshold_days', sa.Integer(), nullable=True),
        sa.Column('notification_email', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'alert_type', name='uq_user_alert_type'),
    )
    op.create_index('ix_alert_configs_user_id', 'alert_configs', ['user_id'])
    op.create_index('ix_alert_configs_alert_type', 'alert_configs', ['alert_type'])


def downgrade() -> None:
    """Drop all tables and enum types."""
    op.drop_table('alert_configs')
    op.drop_table('audit_logs')
    op.drop_table('obligations')
    op.drop_table('clauses')
    op.drop_table('contracts')
    op.drop_table('users')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS alerttype")
    op.execute("DROP TYPE IF EXISTS auditaction")
    op.execute("DROP TYPE IF EXISTS obligationstatus")
    op.execute("DROP TYPE IF EXISTS deadlinetype")
    op.execute("DROP TYPE IF EXISTS obligationtype")
    op.execute("DROP TYPE IF EXISTS clausetype")
    op.execute("DROP TYPE IF EXISTS risklevel")
    op.execute("DROP TYPE IF EXISTS contractstatus")
    op.execute("DROP TYPE IF EXISTS contracttype")
    op.execute("DROP TYPE IF EXISTS role")
