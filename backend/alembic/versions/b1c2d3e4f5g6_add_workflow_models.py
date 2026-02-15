"""Add workflow, event, approval, notification, and integration models

Revision ID: b1c2d3e4f5g6
Revises: 0a96e5f1d35e
Create Date: 2026-02-10 21:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, Sequence[str], None] = '0a96e5f1d35e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add all workflow-related tables."""

    # Create enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventtype AS ENUM (
                'sla_breach', 'sla_warning', 'milestone_approaching', 'milestone_overdue',
                'renewal_approaching', 'renewal_overdue', 'obligation_due', 'obligation_overdue',
                'contract_expiring', 'contract_expired', 'benchmark_window', 'cola_adjustment', 'custom'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventseverity AS ENUM ('info', 'warning', 'critical');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventstatus AS ENUM (
                'pending', 'processing', 'awaiting_approval', 'executing', 'completed', 'failed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE actiontype AS ENUM (
                'send_email', 'send_slack', 'create_snow_incident', 'update_snow_incident',
                'update_sfdc_account', 'create_sfdc_task', 'calculate_service_credit', 'calculate_penalty',
                'update_contract_status', 'update_obligation_status', 'create_approval_request',
                'escalate', 'webhook', 'custom'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE executionstatus AS ENUM (
                'pending', 'pending_approval', 'approved', 'rejected', 'executing',
                'completed', 'failed', 'skipped', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE approvalstatus AS ENUM (
                'pending', 'approved', 'rejected', 'expired', 'escalated', 'delegated'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notificationchannel AS ENUM ('email', 'slack', 'teams', 'webhook');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notificationstatus AS ENUM ('pending', 'sent', 'delivered', 'failed', 'bounced');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE recipienttype AS ENUM (
                'contract_owner', 'vendor_contact', 'approver', 'escalation_contact', 'custom'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE integrationsystem AS ENUM (
                'servicenow', 'salesforce', 'sendgrid', 'smtp', 'slack', 'teams', 'webhook'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE integrationstatus AS ENUM ('healthy', 'degraded', 'unhealthy', 'unknown');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    # Create workflow_definitions table
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflow_definitions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            event_type eventtype NOT NULL,
            version INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT true,
            is_default BOOLEAN DEFAULT false,
            max_retries INTEGER DEFAULT 3,
            retry_delay_seconds INTEGER DEFAULT 60,
            timeout_seconds INTEGER DEFAULT 3600,
            trigger_conditions JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create workflow_steps table
    op.execute("""
        CREATE TABLE IF NOT EXISTS workflow_steps (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            step_order INTEGER NOT NULL,
            action_type actiontype NOT NULL,
            action_config JSONB,
            requires_approval BOOLEAN DEFAULT false,
            approval_timeout_hours INTEGER DEFAULT 24,
            auto_approve_after_timeout BOOLEAN DEFAULT false,
            is_optional BOOLEAN DEFAULT false,
            continue_on_failure BOOLEAN DEFAULT false,
            max_retries INTEGER DEFAULT 3,
            condition JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create events table
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_type eventtype NOT NULL,
            severity eventseverity DEFAULT 'warning',
            contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            obligation_id UUID REFERENCES obligations(id) ON DELETE SET NULL,
            sla_id UUID REFERENCES contract_slas(id) ON DELETE SET NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            details JSONB,
            detected_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            detected_by VARCHAR(100) DEFAULT 'monitor_service',
            status eventstatus DEFAULT 'pending',
            workflow_id UUID REFERENCES workflow_definitions(id) ON DELETE SET NULL,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            error_message TEXT,
            is_duplicate BOOLEAN DEFAULT false,
            original_event_id UUID REFERENCES events(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create action_executions table
    op.execute("""
        CREATE TABLE IF NOT EXISTS action_executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            workflow_step_id UUID REFERENCES workflow_steps(id) ON DELETE SET NULL,
            action_type actiontype NOT NULL,
            action_config JSONB,
            status executionstatus DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            scheduled_at TIMESTAMP WITH TIME ZONE,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            result JSONB,
            error_message TEXT,
            external_id VARCHAR(200),
            trace_id VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create approvers table
    op.execute("""
        CREATE TABLE IF NOT EXISTS approvers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            is_primary BOOLEAN DEFAULT true,
            can_delegate BOOLEAN DEFAULT true,
            approval_order INTEGER DEFAULT 1,
            notify_email BOOLEAN DEFAULT true,
            notify_slack BOOLEAN DEFAULT false,
            is_active BOOLEAN DEFAULT true,
            out_of_office BOOLEAN DEFAULT false,
            delegate_to UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create approval_requests table
    op.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            action_execution_id UUID NOT NULL REFERENCES action_executions(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            context_data JSONB,
            approver_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            original_approver_id UUID REFERENCES users(id) ON DELETE SET NULL,
            status approvalstatus DEFAULT 'pending',
            requested_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            expires_at TIMESTAMP WITH TIME ZONE,
            decided_at TIMESTAMP WITH TIME ZONE,
            decision_notes TEXT,
            rejection_reason TEXT,
            notification_sent BOOLEAN DEFAULT false,
            notification_sent_at TIMESTAMP WITH TIME ZONE,
            reminder_count INTEGER DEFAULT 0,
            last_reminder_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create notification_templates table
    op.execute("""
        CREATE TABLE IF NOT EXISTS notification_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(200) NOT NULL UNIQUE,
            description TEXT,
            event_type eventtype,
            channel notificationchannel DEFAULT 'email',
            subject_template VARCHAR(500) NOT NULL,
            body_template TEXT NOT NULL,
            is_html BOOLEAN DEFAULT true,
            html_template TEXT,
            default_recipient_type recipienttype,
            is_active BOOLEAN DEFAULT true,
            version INTEGER DEFAULT 1,
            available_variables JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create notification_logs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS notification_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            template_id UUID REFERENCES notification_templates(id) ON DELETE SET NULL,
            event_id UUID REFERENCES events(id) ON DELETE SET NULL,
            action_execution_id UUID REFERENCES action_executions(id) ON DELETE SET NULL,
            channel notificationchannel NOT NULL,
            recipient_email VARCHAR(255) NOT NULL,
            recipient_name VARCHAR(255),
            recipient_type recipienttype,
            subject VARCHAR(500) NOT NULL,
            body TEXT NOT NULL,
            variables_used JSONB,
            status notificationstatus DEFAULT 'pending',
            sent_at TIMESTAMP WITH TIME ZONE,
            delivered_at TIMESTAMP WITH TIME ZONE,
            attempts INTEGER DEFAULT 0,
            error_message TEXT,
            last_attempt_at TIMESTAMP WITH TIME ZONE,
            external_id VARCHAR(200),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create integration_configs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS integration_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            system integrationsystem NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            base_url VARCHAR(500) NOT NULL,
            auth_type VARCHAR(50) DEFAULT 'oauth2',
            credentials JSONB,
            config JSONB,
            is_active BOOLEAN DEFAULT true,
            is_default BOOLEAN DEFAULT false,
            health_status integrationstatus DEFAULT 'unknown',
            last_health_check TIMESTAMP WITH TIME ZONE,
            last_health_message TEXT,
            last_used_at TIMESTAMP WITH TIME ZONE,
            total_requests INTEGER DEFAULT 0,
            failed_requests INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create integration_logs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS integration_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            integration_id UUID NOT NULL REFERENCES integration_configs(id) ON DELETE CASCADE,
            action_execution_id UUID REFERENCES action_executions(id) ON DELETE SET NULL,
            operation VARCHAR(100) NOT NULL,
            method VARCHAR(10) NOT NULL,
            endpoint VARCHAR(500) NOT NULL,
            request_payload JSONB,
            status_code INTEGER,
            response_payload JSONB,
            external_id VARCHAR(200),
            started_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            completed_at TIMESTAMP WITH TIME ZONE,
            duration_ms INTEGER,
            is_success BOOLEAN DEFAULT false,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create sla_measurements table
    op.execute("""
        CREATE TABLE IF NOT EXISTS sla_measurements (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sla_id UUID NOT NULL REFERENCES contract_slas(id) ON DELETE CASCADE,
            measurement_date TIMESTAMP WITH TIME ZONE NOT NULL,
            period_start TIMESTAMP WITH TIME ZONE,
            period_end TIMESTAMP WITH TIME ZONE,
            actual_value DOUBLE PRECISION NOT NULL,
            target_value DOUBLE PRECISION NOT NULL,
            is_breach BOOLEAN DEFAULT false,
            deviation_percent DOUBLE PRECISION,
            source VARCHAR(50) DEFAULT 'synthetic',
            source_reference VARCHAR(200),
            event_generated BOOLEAN DEFAULT false,
            event_id UUID REFERENCES events(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_contract ON events(contract_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_status ON events(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_type ON events(event_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_detected ON events(detected_at);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_workflow_steps_workflow ON workflow_steps(workflow_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_action_exec_event ON action_executions(event_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_action_exec_status ON action_executions(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_approval_req_status ON approval_requests(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_approval_req_approver ON approval_requests(approver_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notif_log_event ON notification_logs(event_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notif_log_status ON notification_logs(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_integ_log_integration ON integration_logs(integration_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sla_meas_sla ON sla_measurements(sla_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sla_meas_date ON sla_measurements(measurement_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sla_meas_breach ON sla_measurements(is_breach);")


def downgrade() -> None:
    """Remove all workflow-related tables."""
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_sla_meas_breach;")
    op.execute("DROP INDEX IF EXISTS ix_sla_meas_date;")
    op.execute("DROP INDEX IF EXISTS ix_sla_meas_sla;")
    op.execute("DROP INDEX IF EXISTS ix_integ_log_integration;")
    op.execute("DROP INDEX IF EXISTS ix_notif_log_status;")
    op.execute("DROP INDEX IF EXISTS ix_notif_log_event;")
    op.execute("DROP INDEX IF EXISTS ix_approval_req_approver;")
    op.execute("DROP INDEX IF EXISTS ix_approval_req_status;")
    op.execute("DROP INDEX IF EXISTS ix_action_exec_status;")
    op.execute("DROP INDEX IF EXISTS ix_action_exec_event;")
    op.execute("DROP INDEX IF EXISTS ix_workflow_steps_workflow;")
    op.execute("DROP INDEX IF EXISTS ix_events_detected;")
    op.execute("DROP INDEX IF EXISTS ix_events_type;")
    op.execute("DROP INDEX IF EXISTS ix_events_status;")
    op.execute("DROP INDEX IF EXISTS ix_events_contract;")

    # Drop tables
    op.execute("DROP TABLE IF EXISTS sla_measurements;")
    op.execute("DROP TABLE IF EXISTS integration_logs;")
    op.execute("DROP TABLE IF EXISTS integration_configs;")
    op.execute("DROP TABLE IF EXISTS notification_logs;")
    op.execute("DROP TABLE IF EXISTS notification_templates;")
    op.execute("DROP TABLE IF EXISTS approval_requests;")
    op.execute("DROP TABLE IF EXISTS approvers;")
    op.execute("DROP TABLE IF EXISTS action_executions;")
    op.execute("DROP TABLE IF EXISTS events;")
    op.execute("DROP TABLE IF EXISTS workflow_steps;")
    op.execute("DROP TABLE IF EXISTS workflow_definitions;")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS integrationstatus;")
    op.execute("DROP TYPE IF EXISTS integrationsystem;")
    op.execute("DROP TYPE IF EXISTS recipienttype;")
    op.execute("DROP TYPE IF EXISTS notificationstatus;")
    op.execute("DROP TYPE IF EXISTS notificationchannel;")
    op.execute("DROP TYPE IF EXISTS approvalstatus;")
    op.execute("DROP TYPE IF EXISTS executionstatus;")
    op.execute("DROP TYPE IF EXISTS actiontype;")
    op.execute("DROP TYPE IF EXISTS eventstatus;")
    op.execute("DROP TYPE IF EXISTS eventseverity;")
    op.execute("DROP TYPE IF EXISTS eventtype;")
