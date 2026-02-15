"""Add relationship governance tables (Evaluetor features)

Revision ID: m6n7o8p9q0r1
Revises: l5m6n7o8p9q0
Create Date: 2026-02-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'm6n7o8p9q0r1'
down_revision: Union[str, None] = 'l5m6n7o8p9q0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE organizationtype AS ENUM ('customer', 'vendor', 'partner', 'internal')")
    op.execute("CREATE TYPE organizationsize AS ENUM ('startup', 'smb', 'mid_market', 'enterprise', 'global')")
    op.execute("CREATE TYPE relationshiptype AS ENUM ('customer', 'supplier', 'partner', 'joint_venture', 'reseller', 'distributor')")
    op.execute("CREATE TYPE relationshipstatus AS ENUM ('prospecting', 'active', 'at_risk', 'on_hold', 'terminated')")
    op.execute("CREATE TYPE governancetier AS ENUM ('operational', 'tactical', 'strategic', 'executive')")
    op.execute("CREATE TYPE teamrole AS ENUM ('relationship_manager', 'account_manager', 'executive_sponsor', 'technical_lead', 'operations_lead', 'finance_lead', 'member')")
    op.execute("CREATE TYPE kpimeasurementtype AS ENUM ('percentage', 'number', 'currency', 'time_hours', 'time_days', 'rating', 'boolean')")
    op.execute("CREATE TYPE kpicategory AS ENUM ('service_delivery', 'quality', 'timeliness', 'communication', 'innovation', 'cost_efficiency', 'compliance', 'satisfaction', 'other')")
    op.execute("CREATE TYPE gapseverity AS ENUM ('minor', 'moderate', 'significant', 'critical')")
    op.execute("CREATE TYPE improvementpriority AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE improvementstatus AS ENUM ('open', 'in_progress', 'blocked', 'completed', 'cancelled')")
    op.execute("CREATE TYPE improvementsource AS ENUM ('perception_gap', 'sla_breach', 'review_meeting', 'customer_feedback', 'internal_audit', 'manual')")
    op.execute("CREATE TYPE actionstatus AS ENUM ('todo', 'in_progress', 'completed', 'blocked', 'cancelled')")
    op.execute("CREATE TYPE surveyfrequency AS ENUM ('one_time', 'monthly', 'quarterly', 'semi_annual', 'annual')")
    op.execute("CREATE TYPE questiontype AS ENUM ('rating', 'rating_5', 'multiple_choice', 'single_choice', 'text', 'text_long', 'yes_no', 'nps')")
    op.execute("CREATE TYPE surveystatus AS ENUM ('draft', 'scheduled', 'sent', 'in_progress', 'completed', 'expired', 'cancelled')")
    op.execute("CREATE TYPE tokentype AS ENUM ('perception_scoring', 'survey_response', 'document_view', 'multi_purpose')")

    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False, unique=True),
        sa.Column('org_type', postgresql.ENUM('customer', 'vendor', 'partner', 'internal', name='organizationtype', create_type=False), nullable=False, server_default='customer'),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('size', postgresql.ENUM('startup', 'smb', 'mid_market', 'enterprise', 'global', name='organizationsize', create_type=False), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('website', sa.String(255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('primary_contact_name', sa.String(255), nullable=True),
        sa.Column('primary_contact_email', sa.String(255), nullable=True),
        sa.Column('primary_contact_phone', sa.String(50), nullable=True),
        sa.Column('relationship_owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_organizations_name', 'organizations', ['name'])
    op.create_index('ix_organizations_code', 'organizations', ['code'])

    # Create business_relationships table
    op.create_table(
        'business_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_a_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('org_b_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('relationship_type', postgresql.ENUM('customer', 'supplier', 'partner', 'joint_venture', 'reseller', 'distributor', name='relationshiptype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('prospecting', 'active', 'at_risk', 'on_hold', 'terminated', name='relationshipstatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('health_score', sa.Integer(), nullable=True),
        sa.Column('last_health_calculation', sa.DateTime(), nullable=True),
        sa.Column('governance_tier', postgresql.ENUM('operational', 'tactical', 'strategic', 'executive', name='governancetier', create_type=False), nullable=True, server_default='operational'),
        sa.Column('governance_config', postgresql.JSONB(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('review_frequency_days', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('next_review_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_business_relationships_org_a', 'business_relationships', ['org_a_id'])
    op.create_index('ix_business_relationships_org_b', 'business_relationships', ['org_b_id'])

    # Create relationship_teams table
    op.create_table(
        'relationship_teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_relationships.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', postgresql.ENUM('relationship_manager', 'account_manager', 'executive_sponsor', 'technical_lead', 'operations_lead', 'finance_lead', 'member', name='teamrole', create_type=False), nullable=False, server_default='member'),
        sa.Column('responsibilities', postgresql.JSONB(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('left_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_relationship_teams_relationship', 'relationship_teams', ['relationship_id'])
    op.create_index('ix_relationship_teams_user', 'relationship_teams', ['user_id'])

    # Create kpis table
    op.create_table(
        'kpis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_relationships.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', postgresql.ENUM('service_delivery', 'quality', 'timeliness', 'communication', 'innovation', 'cost_efficiency', 'compliance', 'satisfaction', 'other', name='kpicategory', create_type=False), nullable=False, server_default='other'),
        sa.Column('measurement_type', postgresql.ENUM('percentage', 'number', 'currency', 'time_hours', 'time_days', 'rating', 'boolean', name='kpimeasurementtype', create_type=False), nullable=False, server_default='rating'),
        sa.Column('target_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('minimum_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('threshold_amber', sa.Numeric(12, 2), nullable=True),
        sa.Column('threshold_red', sa.Numeric(12, 2), nullable=True),
        sa.Column('weight', sa.Numeric(5, 2), nullable=True, server_default='1.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_perception_based', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_kpis_relationship', 'kpis', ['relationship_id'])

    # Create perception_scores table
    op.create_table(
        'perception_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kpi_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kpis.id'), nullable=False),
        sa.Column('scorer_org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('scored_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('score', sa.Numeric(5, 2), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('is_internal', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('scored_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_perception_scores_kpi', 'perception_scores', ['kpi_id'])
    op.create_index('ix_perception_scores_period', 'perception_scores', ['period'])

    # Create perception_gaps table
    op.create_table(
        'perception_gaps',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('kpi_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kpis.id'), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('internal_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('external_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('gap', sa.Numeric(5, 2), nullable=True),
        sa.Column('gap_severity', postgresql.ENUM('minor', 'moderate', 'significant', 'critical', name='gapseverity', create_type=False), nullable=True),
        sa.Column('requires_action', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_perception_gaps_kpi', 'perception_gaps', ['kpi_id'])
    op.create_index('ix_perception_gaps_period', 'perception_gaps', ['period'])

    # Create improvement_points table
    op.create_table(
        'improvement_points',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_relationships.id'), nullable=False),
        sa.Column('kpi_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kpis.id'), nullable=True),
        sa.Column('gap_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('perception_gaps.id'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', postgresql.ENUM('perception_gap', 'sla_breach', 'review_meeting', 'customer_feedback', 'internal_audit', 'manual', name='improvementsource', create_type=False), nullable=False, server_default='manual'),
        sa.Column('priority', postgresql.ENUM('low', 'medium', 'high', 'critical', name='improvementpriority', create_type=False), nullable=False, server_default='medium'),
        sa.Column('status', postgresql.ENUM('open', 'in_progress', 'blocked', 'completed', 'cancelled', name='improvementstatus', create_type=False), nullable=False, server_default='open'),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('assigned_org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('target_outcome', sa.Text(), nullable=True),
        sa.Column('actual_outcome', sa.Text(), nullable=True),
        sa.Column('impact_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_improvement_points_relationship', 'improvement_points', ['relationship_id'])
    op.create_index('ix_improvement_points_status', 'improvement_points', ['status'])

    # Create improvement_actions table
    op.create_table(
        'improvement_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('improvement_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('improvement_points.id'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('todo', 'in_progress', 'completed', 'blocked', 'cancelled', name='actionstatus', create_type=False), nullable=False, server_default='todo'),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('blocker_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_improvement_actions_improvement', 'improvement_actions', ['improvement_id'])

    # Create survey_templates table
    op.create_table(
        'survey_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('frequency', postgresql.ENUM('one_time', 'monthly', 'quarterly', 'semi_annual', 'annual', name='surveyfrequency', create_type=False), nullable=False, server_default='quarterly'),
        sa.Column('introduction_text', sa.Text(), nullable=True),
        sa.Column('closing_text', sa.Text(), nullable=True),
        sa.Column('allow_anonymous', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('require_all_questions', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create survey_questions table
    op.create_table(
        'survey_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('survey_templates.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('question_type', postgresql.ENUM('rating', 'rating_5', 'multiple_choice', 'single_choice', 'text', 'text_long', 'yes_no', 'nps', name='questiontype', create_type=False), nullable=False, server_default='rating'),
        sa.Column('options', postgresql.JSONB(), nullable=True),
        sa.Column('rating_min_label', sa.String(100), nullable=True),
        sa.Column('rating_max_label', sa.String(100), nullable=True),
        sa.Column('kpi_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kpis.id'), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_survey_questions_template', 'survey_questions', ['template_id'])

    # Create survey_instances table
    op.create_table(
        'survey_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('survey_templates.id'), nullable=False),
        sa.Column('relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_relationships.id'), nullable=False),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('status', postgresql.ENUM('draft', 'scheduled', 'sent', 'in_progress', 'completed', 'expired', 'cancelled', name='surveystatus', create_type=False), nullable=False, server_default='draft'),
        sa.Column('scheduled_send_date', sa.Date(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('target_respondent_count', sa.Integer(), nullable=True),
        sa.Column('actual_respondent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_survey_instances_relationship', 'survey_instances', ['relationship_id'])
    op.create_index('ix_survey_instances_period', 'survey_instances', ['period'])

    # Create survey_responses table
    op.create_table(
        'survey_responses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('survey_instance_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('survey_instances.id'), nullable=False),
        sa.Column('respondent_email', sa.String(255), nullable=True),
        sa.Column('respondent_name', sa.String(255), nullable=True),
        sa.Column('respondent_org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('answers', postgresql.JSONB(), nullable=False),
        sa.Column('completion_time_seconds', sa.Integer(), nullable=True),
        sa.Column('is_complete', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('access_token', sa.String(100), nullable=True, unique=True),
        sa.Column('first_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_survey_responses_instance', 'survey_responses', ['survey_instance_id'])

    # Create external_access_tokens table
    op.create_table(
        'external_access_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('token', sa.String(100), nullable=False, unique=True),
        sa.Column('token_type', postgresql.ENUM('perception_scoring', 'survey_response', 'document_view', 'multi_purpose', name='tokentype', create_type=False), nullable=False),
        sa.Column('relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_relationships.id'), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('survey_instance_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('survey_instances.id'), nullable=True),
        sa.Column('recipient_email', sa.String(255), nullable=True),
        sa.Column('recipient_name', sa.String(255), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_reason', sa.Text(), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_used_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_external_access_tokens_token', 'external_access_tokens', ['token'])

    # Add business_relationship_id to contracts table
    op.add_column('contracts', sa.Column('business_relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_relationships.id'), nullable=True))
    op.create_index('ix_contracts_business_relationship', 'contracts', ['business_relationship_id'])


def downgrade() -> None:
    # Remove business_relationship_id from contracts
    op.drop_index('ix_contracts_business_relationship', table_name='contracts')
    op.drop_column('contracts', 'business_relationship_id')

    # Drop tables in reverse order
    op.drop_index('ix_external_access_tokens_token', table_name='external_access_tokens')
    op.drop_table('external_access_tokens')

    op.drop_index('ix_survey_responses_instance', table_name='survey_responses')
    op.drop_table('survey_responses')

    op.drop_index('ix_survey_instances_period', table_name='survey_instances')
    op.drop_index('ix_survey_instances_relationship', table_name='survey_instances')
    op.drop_table('survey_instances')

    op.drop_index('ix_survey_questions_template', table_name='survey_questions')
    op.drop_table('survey_questions')

    op.drop_table('survey_templates')

    op.drop_index('ix_improvement_actions_improvement', table_name='improvement_actions')
    op.drop_table('improvement_actions')

    op.drop_index('ix_improvement_points_status', table_name='improvement_points')
    op.drop_index('ix_improvement_points_relationship', table_name='improvement_points')
    op.drop_table('improvement_points')

    op.drop_index('ix_perception_gaps_period', table_name='perception_gaps')
    op.drop_index('ix_perception_gaps_kpi', table_name='perception_gaps')
    op.drop_table('perception_gaps')

    op.drop_index('ix_perception_scores_period', table_name='perception_scores')
    op.drop_index('ix_perception_scores_kpi', table_name='perception_scores')
    op.drop_table('perception_scores')

    op.drop_index('ix_kpis_relationship', table_name='kpis')
    op.drop_table('kpis')

    op.drop_index('ix_relationship_teams_user', table_name='relationship_teams')
    op.drop_index('ix_relationship_teams_relationship', table_name='relationship_teams')
    op.drop_table('relationship_teams')

    op.drop_index('ix_business_relationships_org_b', table_name='business_relationships')
    op.drop_index('ix_business_relationships_org_a', table_name='business_relationships')
    op.drop_table('business_relationships')

    op.drop_index('ix_organizations_code', table_name='organizations')
    op.drop_index('ix_organizations_name', table_name='organizations')
    op.drop_table('organizations')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS tokentype")
    op.execute("DROP TYPE IF EXISTS surveystatus")
    op.execute("DROP TYPE IF EXISTS questiontype")
    op.execute("DROP TYPE IF EXISTS surveyfrequency")
    op.execute("DROP TYPE IF EXISTS actionstatus")
    op.execute("DROP TYPE IF EXISTS improvementsource")
    op.execute("DROP TYPE IF EXISTS improvementstatus")
    op.execute("DROP TYPE IF EXISTS improvementpriority")
    op.execute("DROP TYPE IF EXISTS gapseverity")
    op.execute("DROP TYPE IF EXISTS kpicategory")
    op.execute("DROP TYPE IF EXISTS kpimeasurementtype")
    op.execute("DROP TYPE IF EXISTS teamrole")
    op.execute("DROP TYPE IF EXISTS governancetier")
    op.execute("DROP TYPE IF EXISTS relationshipstatus")
    op.execute("DROP TYPE IF EXISTS relationshiptype")
    op.execute("DROP TYPE IF EXISTS organizationsize")
    op.execute("DROP TYPE IF EXISTS organizationtype")
