"""add sla_alerts table

Revision ID: k4l5m6n7o8p9
Revises: j3k4l5m6n7o8
Create Date: 2025-01-20 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'k4l5m6n7o8p9'
down_revision: Union[str, None] = 'j3k4l5m6n7o8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types if they don't exist (handles SQLAlchemy auto-creation)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertpriority') THEN
                CREATE TYPE alertpriority AS ENUM ('low', 'medium', 'high', 'critical');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertstatus') THEN
                CREATE TYPE alertstatus AS ENUM ('active', 'acknowledged', 'in_progress', 'resolved', 'dismissed', 'escalated');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertcategory') THEN
                CREATE TYPE alertcategory AS ENUM ('sla_breach', 'sla_warning', 'sla_improvement', 'milestone_delayed', 'milestone_at_risk', 'fx_threshold', 'service_credit', 'contract_expiry', 'obligation_due');
            END IF;
        END $$;
    """)

    # Create sla_alerts table
    op.create_table(
        'sla_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sla_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('performance_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('category', postgresql.ENUM('sla_breach', 'sla_warning', 'sla_improvement', 'milestone_delayed', 'milestone_at_risk', 'fx_threshold', 'service_credit', 'contract_expiry', 'obligation_due', name='alertcategory', create_type=False), nullable=False),
        sa.Column('priority', postgresql.ENUM('low', 'medium', 'high', 'critical', name='alertpriority', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'acknowledged', 'in_progress', 'resolved', 'dismissed', 'escalated', name='alertstatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('sla_reference', sa.String(50), nullable=True),
        sa.Column('sla_name', sa.String(200), nullable=True),
        sa.Column('target_value', sa.Numeric(10, 4), nullable=True),
        sa.Column('minimum_value', sa.Numeric(10, 4), nullable=True),
        sa.Column('actual_value', sa.Numeric(10, 4), nullable=True),
        sa.Column('deviation_percentage', sa.Numeric(8, 2), nullable=True),
        sa.Column('breach_severity', postgresql.ENUM('minor', 'moderate', 'major', 'critical', name='breachseverity', create_type=False), nullable=True),
        sa.Column('has_financial_impact', sa.Boolean(), nullable=False, default=False),
        sa.Column('estimated_credit', sa.Numeric(12, 2), nullable=True),
        sa.Column('at_risk_amount', sa.Numeric(12, 2), nullable=True),
        sa.Column('measurement_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('measurement_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('escalation_level', sa.Integer(), nullable=False, default=0),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escalated_to', sa.String(255), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('notification_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_log_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_system', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sla_id'], ['contract_slas.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['performance_id'], ['sla_performances.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['notification_log_id'], ['notification_logs.id'], ondelete='SET NULL'),
    )

    # Create indexes for common queries
    op.create_index('ix_sla_alerts_contract_id', 'sla_alerts', ['contract_id'])
    op.create_index('ix_sla_alerts_sla_id', 'sla_alerts', ['sla_id'])
    op.create_index('ix_sla_alerts_category', 'sla_alerts', ['category'])
    op.create_index('ix_sla_alerts_priority', 'sla_alerts', ['priority'])
    op.create_index('ix_sla_alerts_status', 'sla_alerts', ['status'])
    op.create_index('ix_sla_alerts_detected_at', 'sla_alerts', ['detected_at'])
    op.create_index('ix_sla_alerts_priority_status', 'sla_alerts', ['priority', 'status'])

    # Insert default notification templates for SLA alerts
    op.execute("""
        INSERT INTO notification_templates (id, name, description, channel, subject_template, body_template, is_html, is_active, version, available_variables, created_at, updated_at)
        VALUES
        (
            gen_random_uuid(),
            'sla_breach_alert',
            'Alert notification for SLA breaches',
            'email',
            '[{{ priority | upper }}] SLA BREACH: {{ sla_name }} - {{ contract_name }}',
            'Dear {{ recipient_name }},

An SLA breach has been detected that requires your attention.

ALERT DETAILS
=============
Contract: {{ contract_name }}
SLA: {{ sla_name }} ({{ sla_reference }})
Priority: {{ priority | upper }}
Severity: {{ breach_severity | upper }}

PERFORMANCE DATA
================
Target Value: {{ target_value }}%
Actual Value: {{ actual_value }}%
Deviation: {{ deviation_percent }}%

{% if has_financial_impact %}
FINANCIAL IMPACT
================
Service Credit Due: {{ credit_amount }}%
At-Risk Amount: {{ at_risk_amount }}%
{% endif %}

Detected: {{ detected_at }}
Source: {{ source_system }}

Please review this breach and take appropriate action.

---
Contract Intelligence Platform',
            false,
            true,
            1,
            '{"recipient_name": "string", "contract_name": "string", "sla_name": "string", "sla_reference": "string", "priority": "string", "breach_severity": "string", "target_value": "number", "actual_value": "number", "deviation_percent": "number", "has_financial_impact": "boolean", "credit_amount": "number", "at_risk_amount": "number", "detected_at": "string", "source_system": "string"}',
            now(),
            now()
        ),
        (
            gen_random_uuid(),
            'sla_warning_alert',
            'Warning notification when SLA is below target but above minimum',
            'email',
            '[WARNING] SLA Performance: {{ sla_name }} - {{ contract_name }}',
            'Dear {{ recipient_name }},

An SLA warning has been detected.

ALERT DETAILS
=============
Contract: {{ contract_name }}
SLA: {{ sla_name }} ({{ sla_reference }})
Status: Below target, above minimum

PERFORMANCE DATA
================
Target Value: {{ target_value }}%
Actual Value: {{ actual_value }}%
Deviation from Target: {{ deviation_percent }}%

This SLA is currently meeting minimum requirements but is below target. Proactive action is recommended to prevent a potential breach.

Detected: {{ detected_at }}

---
Contract Intelligence Platform',
            false,
            true,
            1,
            '{"recipient_name": "string", "contract_name": "string", "sla_name": "string", "sla_reference": "string", "target_value": "number", "actual_value": "number", "deviation_percent": "number", "detected_at": "string"}',
            now(),
            now()
        ),
        (
            gen_random_uuid(),
            'alert_escalation',
            'Notification when an alert is escalated',
            'email',
            '[ESCALATION LEVEL {{ escalation_level }}] {{ title }}',
            'Dear Escalation Contact,

An alert has been escalated to your attention.

ESCALATION DETAILS
==================
Level: {{ escalation_level }}
Priority: {{ priority | upper }}
Days Open: {{ days_open }}

ALERT INFORMATION
=================
{{ title }}

{{ description }}

This alert requires immediate attention. Please review and take appropriate action.

---
Contract Intelligence Platform',
            false,
            true,
            1,
            '{"escalation_level": "number", "title": "string", "description": "string", "priority": "string", "days_open": "number"}',
            now(),
            now()
        ),
        (
            gen_random_uuid(),
            'service_credit_notification',
            'Notification when service credit is due',
            'email',
            'Service Credit Due: {{ sla_name }} - {{ contract_name }}',
            'Dear {{ recipient_name }},

A service credit is due based on SLA performance.

CREDIT DETAILS
==============
Contract: {{ contract_name }}
SLA: {{ sla_name }} ({{ sla_reference }})
Breach Severity: {{ breach_severity | upper }}

CALCULATION
===========
At-Risk Pool: {{ at_risk_percentage }}%
Credit Rate: {{ credit_rate }}%
Credit Due: {{ credit_amount }}%

This credit should be applied to the next invoice per contract terms.

---
Contract Intelligence Platform',
            false,
            true,
            1,
            '{"recipient_name": "string", "contract_name": "string", "sla_name": "string", "sla_reference": "string", "breach_severity": "string", "at_risk_percentage": "number", "credit_rate": "number", "credit_amount": "number"}',
            now(),
            now()
        )
        ON CONFLICT (name) DO NOTHING;
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_sla_alerts_priority_status')
    op.drop_index('ix_sla_alerts_detected_at')
    op.drop_index('ix_sla_alerts_status')
    op.drop_index('ix_sla_alerts_priority')
    op.drop_index('ix_sla_alerts_category')
    op.drop_index('ix_sla_alerts_sla_id')
    op.drop_index('ix_sla_alerts_contract_id')

    # Drop table
    op.drop_table('sla_alerts')

    # Drop enum types
    op.execute("DROP TYPE alertcategory")
    op.execute("DROP TYPE alertstatus")
    op.execute("DROP TYPE alertpriority")
