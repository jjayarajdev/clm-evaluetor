"""Add SLA tables

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-02-01 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add contract_slas and sla_performances tables."""

    # Create enums
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE slametrictype AS ENUM (
                'uptime_percentage', 'response_time', 'resolution_time',
                'delivery_time', 'throughput', 'error_rate',
                'availability', 'quality_score', 'custom'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE slaunit AS ENUM (
                'percentage', 'hours', 'minutes', 'days',
                'business_days', 'count', 'score'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE slaseverity AS ENUM ('critical', 'high', 'medium', 'low');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE breachseverity AS ENUM ('minor', 'moderate', 'major', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create contract_slas table using raw SQL to avoid SQLAlchemy enum auto-creation
    op.execute("""
        CREATE TABLE contract_slas (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
            source_clause_id UUID REFERENCES clauses(id) ON DELETE SET NULL,
            sla_name VARCHAR(200) NOT NULL,
            sla_description TEXT,
            metric_type slametrictype NOT NULL,
            metric_unit slaunit NOT NULL,
            target_value NUMERIC(10, 2) NOT NULL,
            target_operator VARCHAR(10) NOT NULL DEFAULT '>=',
            warning_threshold NUMERIC(10, 2),
            severity slaseverity NOT NULL,
            has_penalty BOOLEAN NOT NULL DEFAULT false,
            penalty_type VARCHAR(50),
            penalty_value NUMERIC(15, 2),
            penalty_description TEXT,
            max_penalty_cap NUMERIC(15, 2),
            measurement_period VARCHAR(50),
            measurement_start DATE,
            is_active BOOLEAN NOT NULL DEFAULT true,
            current_compliance_rate NUMERIC(5, 2),
            last_measured_at TIMESTAMP WITH TIME ZONE,
            consecutive_breaches INTEGER NOT NULL DEFAULT 0,
            source_text TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.create_index('ix_sla_contract_metric', 'contract_slas', ['contract_id', 'metric_type'])
    op.create_index('ix_sla_severity', 'contract_slas', ['severity'])
    op.create_index('ix_sla_active', 'contract_slas', ['is_active'])

    # Create sla_performances table using raw SQL
    op.execute("""
        CREATE TABLE sla_performances (
            id UUID DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
            sla_id UUID NOT NULL REFERENCES contract_slas(id) ON DELETE CASCADE,
            actual_value NUMERIC(10, 2) NOT NULL,
            measured_at TIMESTAMP WITH TIME ZONE NOT NULL,
            measurement_period_start DATE,
            measurement_period_end DATE,
            is_compliant BOOLEAN NOT NULL,
            deviation_percentage NUMERIC(10, 2),
            breach_severity breachseverity,
            penalty_applied BOOLEAN NOT NULL DEFAULT false,
            penalty_amount NUMERIC(15, 2),
            credit_issued NUMERIC(15, 2),
            notes TEXT,
            recorded_by VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.create_index('ix_sla_perf_sla_date', 'sla_performances', ['sla_id', 'measured_at'])
    op.create_index('ix_sla_perf_compliant', 'sla_performances', ['is_compliant'])
    op.create_index('ix_sla_perf_breach', 'sla_performances', ['breach_severity'])


def downgrade() -> None:
    """Remove SLA tables."""
    op.drop_index('ix_sla_perf_breach', table_name='sla_performances')
    op.drop_index('ix_sla_perf_compliant', table_name='sla_performances')
    op.drop_index('ix_sla_perf_sla_date', table_name='sla_performances')
    op.drop_table('sla_performances')

    op.drop_index('ix_sla_active', table_name='contract_slas')
    op.drop_index('ix_sla_severity', table_name='contract_slas')
    op.drop_index('ix_sla_contract_metric', table_name='contract_slas')
    op.drop_table('contract_slas')

    op.execute("DROP TYPE IF EXISTS breachseverity")
    op.execute("DROP TYPE IF EXISTS slaseverity")
    op.execute("DROP TYPE IF EXISTS slaunit")
    op.execute("DROP TYPE IF EXISTS slametrictype")
