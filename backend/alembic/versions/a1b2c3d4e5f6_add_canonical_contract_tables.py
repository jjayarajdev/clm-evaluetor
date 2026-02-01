"""Add canonical contract tables for super model

Revision ID: a1b2c3d4e5f6
Revises: 5c74dd1d4238
Create Date: 2026-02-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5c74dd1d4238'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create canonical contract tables and add new obligation fields."""

    # ===== CREATE ENUM TYPES =====

    # Financial enums
    op.execute("""
        CREATE TYPE feetype AS ENUM (
            'base_fee', 'per_unit', 'per_hour', 'per_day', 'percentage',
            'milestone', 'recurring_monthly', 'recurring_annual', 'one_time',
            'retainer', 'success_fee', 'licensing_fee', 'maintenance_fee',
            'support_fee', 'other'
        )
    """)

    op.execute("""
        CREATE TYPE paymentterms AS ENUM (
            'upon_receipt', 'net_15', 'net_30', 'net_45', 'net_60', 'net_90',
            'advance', 'milestone_based', 'upon_completion', 'custom'
        )
    """)

    op.execute("""
        CREATE TYPE penaltytype AS ENUM (
            'late_payment', 'late_delivery', 'non_compliance', 'breach',
            'early_termination', 'sla_violation', 'quality_failure', 'other'
        )
    """)

    op.execute("""
        CREATE TYPE liabilitycaptype AS ENUM (
            'none', 'unlimited', 'fixed_amount', 'fees_paid', 'annual_fees',
            'multiple_of_fees', 'percentage_of_value', 'insurance_limit', 'custom'
        )
    """)

    # Contract link enum
    op.execute("""
        CREATE TYPE linktype AS ENUM (
            'sow', 'work_order', 'service_order', 'purchase_order',
            'amendment', 'addendum', 'change_order', 'modification', 'renewal',
            'exhibit', 'schedule', 'appendix', 'attachment',
            'supersedes', 'references', 'related'
        )
    """)

    # Obligation enums
    op.execute("""
        CREATE TYPE obligationowner AS ENUM (
            'provider', 'client', 'mutual', 'third_party', 'unspecified'
        )
    """)

    op.execute("""
        CREATE TYPE obligationcategory AS ENUM (
            'service_provision', 'service_levels', 'delivery', 'performance',
            'payment', 'invoicing', 'pricing',
            'data_protection', 'data_handling', 'reporting', 'information_provision', 'record_keeping',
            'regulatory_compliance', 'audit', 'certification', 'insurance',
            'confidentiality', 'ip_protection',
            'notification', 'approval', 'cooperation',
            'staffing', 'training', 'documentation', 'maintenance', 'support', 'testing', 'quality_assurance',
            'transition', 'exit_management', 'return_of_materials',
            'branding', 'marketing', 'collaboration', 'other'
        )
    """)

    op.execute("""
        CREATE TYPE obligationfrequency AS ENUM (
            'one_time', 'daily', 'weekly', 'monthly', 'quarterly',
            'semi_annual', 'annual', 'ongoing', 'triggered', 'as_needed', 'custom'
        )
    """)

    op.execute("""
        CREATE TYPE ragstatus AS ENUM (
            'green', 'amber', 'red', 'not_assessed'
        )
    """)

    # ===== CREATE contract_financials TABLE =====
    op.create_table(
        'contract_financials',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fee_type', postgresql.ENUM('base_fee', 'per_unit', 'per_hour', 'per_day', 'percentage', 'milestone', 'recurring_monthly', 'recurring_annual', 'one_time', 'retainer', 'success_fee', 'licensing_fee', 'maintenance_fee', 'support_fee', 'other', name='feetype', create_type=False), nullable=False, server_default='other'),
        sa.Column('fee_description', sa.String(500), nullable=True),
        sa.Column('fee_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('unit_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('payment_terms', postgresql.ENUM('upon_receipt', 'net_15', 'net_30', 'net_45', 'net_60', 'net_90', 'advance', 'milestone_based', 'upon_completion', 'custom', name='paymentterms', create_type=False), nullable=True),
        sa.Column('payment_terms_days', sa.Integer(), nullable=True),
        sa.Column('payment_trigger', sa.String(255), nullable=True),
        sa.Column('invoicing_frequency', sa.String(100), nullable=True),
        sa.Column('is_penalty', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('penalty_type', postgresql.ENUM('late_payment', 'late_delivery', 'non_compliance', 'breach', 'early_termination', 'sla_violation', 'quality_failure', 'other', name='penaltytype', create_type=False), nullable=True),
        sa.Column('penalty_trigger', sa.Text(), nullable=True),
        sa.Column('penalty_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('penalty_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('section_reference', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_contract_financials_contract_id', 'contract_financials', ['contract_id'])
    op.create_index('ix_contract_financials_fee_type', 'contract_financials', ['fee_type'])

    # ===== CREATE contract_liabilities TABLE =====
    op.create_table(
        'contract_liabilities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('liability_cap_type', postgresql.ENUM('none', 'unlimited', 'fixed_amount', 'fees_paid', 'annual_fees', 'multiple_of_fees', 'percentage_of_value', 'insurance_limit', 'custom', name='liabilitycaptype', create_type=False), nullable=True),
        sa.Column('liability_cap_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('liability_cap_currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('liability_cap_description', sa.Text(), nullable=True),
        sa.Column('liability_cap_multiplier', sa.Numeric(5, 2), nullable=True),
        sa.Column('excludes_direct_damages', sa.Boolean(), nullable=True),
        sa.Column('excludes_indirect_damages', sa.Boolean(), nullable=True),
        sa.Column('excludes_consequential_damages', sa.Boolean(), nullable=True),
        sa.Column('excludes_lost_profits', sa.Boolean(), nullable=True),
        sa.Column('exclusions_description', sa.Text(), nullable=True),
        sa.Column('indemnifying_party', sa.String(255), nullable=True),
        sa.Column('indemnified_party', sa.String(255), nullable=True),
        sa.Column('indemnification_scope', sa.Text(), nullable=True),
        sa.Column('mutual_indemnification', sa.Boolean(), nullable=True),
        sa.Column('insurance_required', sa.Boolean(), nullable=True),
        sa.Column('insurance_types', sa.Text(), nullable=True),
        sa.Column('insurance_minimum_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('section_reference', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_contract_liabilities_contract_id', 'contract_liabilities', ['contract_id'])

    # ===== CREATE contract_clause_indicators TABLE =====
    op.create_table(
        'contract_clause_indicators',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False, unique=True),
        # Confidentiality & IP
        sa.Column('has_confidentiality', sa.Boolean(), nullable=True),
        sa.Column('confidentiality_term_years', sa.Integer(), nullable=True),
        sa.Column('has_mutual_confidentiality', sa.Boolean(), nullable=True),
        sa.Column('has_ip_ownership', sa.Boolean(), nullable=True),
        sa.Column('ip_ownership_party', sa.String(100), nullable=True),
        sa.Column('has_ip_license', sa.Boolean(), nullable=True),
        sa.Column('has_work_for_hire', sa.Boolean(), nullable=True),
        # Liability & Indemnification
        sa.Column('has_limitation_of_liability', sa.Boolean(), nullable=True),
        sa.Column('has_liability_cap', sa.Boolean(), nullable=True),
        sa.Column('has_indemnification', sa.Boolean(), nullable=True),
        sa.Column('has_mutual_indemnification', sa.Boolean(), nullable=True),
        sa.Column('has_warranty_disclaimer', sa.Boolean(), nullable=True),
        sa.Column('has_as_is_disclaimer', sa.Boolean(), nullable=True),
        # Termination & Renewal
        sa.Column('has_termination_for_cause', sa.Boolean(), nullable=True),
        sa.Column('has_termination_for_convenience', sa.Boolean(), nullable=True),
        sa.Column('has_termination_notice_period', sa.Boolean(), nullable=True),
        sa.Column('has_auto_renewal', sa.Boolean(), nullable=True),
        sa.Column('has_renewal_notice_requirement', sa.Boolean(), nullable=True),
        # Force Majeure & Disputes
        sa.Column('has_force_majeure', sa.Boolean(), nullable=True),
        sa.Column('has_governing_law', sa.Boolean(), nullable=True),
        sa.Column('has_dispute_resolution', sa.Boolean(), nullable=True),
        sa.Column('has_arbitration', sa.Boolean(), nullable=True),
        sa.Column('has_mediation', sa.Boolean(), nullable=True),
        sa.Column('has_exclusive_jurisdiction', sa.Boolean(), nullable=True),
        # Compliance & Regulatory
        sa.Column('has_data_protection', sa.Boolean(), nullable=True),
        sa.Column('has_gdpr_compliance', sa.Boolean(), nullable=True),
        sa.Column('has_ccpa_compliance', sa.Boolean(), nullable=True),
        sa.Column('has_hipaa_compliance', sa.Boolean(), nullable=True),
        sa.Column('has_pci_compliance', sa.Boolean(), nullable=True),
        sa.Column('has_soc2_compliance', sa.Boolean(), nullable=True),
        sa.Column('has_anticorruption', sa.Boolean(), nullable=True),
        sa.Column('has_fcpa_compliance', sa.Boolean(), nullable=True),
        sa.Column('has_sanctions_compliance', sa.Boolean(), nullable=True),
        sa.Column('has_export_control', sa.Boolean(), nullable=True),
        # Business Restrictions
        sa.Column('has_non_compete', sa.Boolean(), nullable=True),
        sa.Column('non_compete_duration_months', sa.Integer(), nullable=True),
        sa.Column('has_non_solicit', sa.Boolean(), nullable=True),
        sa.Column('non_solicit_duration_months', sa.Integer(), nullable=True),
        sa.Column('has_exclusivity', sa.Boolean(), nullable=True),
        sa.Column('has_most_favored_nation', sa.Boolean(), nullable=True),
        # Operational
        sa.Column('has_insurance_requirement', sa.Boolean(), nullable=True),
        sa.Column('has_audit_rights', sa.Boolean(), nullable=True),
        sa.Column('has_service_levels', sa.Boolean(), nullable=True),
        sa.Column('has_sla_credits', sa.Boolean(), nullable=True),
        sa.Column('has_change_control', sa.Boolean(), nullable=True),
        sa.Column('has_assignment_restriction', sa.Boolean(), nullable=True),
        sa.Column('has_subcontracting_restriction', sa.Boolean(), nullable=True),
        # Payment
        sa.Column('has_payment_terms', sa.Boolean(), nullable=True),
        sa.Column('has_late_payment_interest', sa.Boolean(), nullable=True),
        sa.Column('has_price_escalation', sa.Boolean(), nullable=True),
        sa.Column('has_taxes_clause', sa.Boolean(), nullable=True),
        # Survival
        sa.Column('has_survival_clause', sa.Boolean(), nullable=True),
        sa.Column('survival_sections', sa.Text(), nullable=True),
        # Notes
        sa.Column('extraction_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_contract_clause_indicators_contract_id', 'contract_clause_indicators', ['contract_id'])

    # ===== CREATE contract_links TABLE =====
    op.create_table(
        'contract_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('parent_contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('child_contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('link_type', postgresql.ENUM('sow', 'work_order', 'service_order', 'purchase_order', 'amendment', 'addendum', 'change_order', 'modification', 'renewal', 'exhibit', 'schedule', 'appendix', 'attachment', 'supersedes', 'references', 'related', name='linktype', create_type=False), nullable=False, server_default='related'),
        sa.Column('link_description', sa.String(500), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('reference_number', sa.String(100), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('parent_contract_id', 'child_contract_id', 'link_type', name='uq_contract_link'),
    )
    op.create_index('ix_contract_links_parent', 'contract_links', ['parent_contract_id'])
    op.create_index('ix_contract_links_child', 'contract_links', ['child_contract_id'])
    op.create_index('ix_contract_links_type', 'contract_links', ['link_type'])

    # ===== ADD NEW COLUMNS TO obligations TABLE =====
    op.add_column('obligations', sa.Column('owner_type', postgresql.ENUM('provider', 'client', 'mutual', 'third_party', 'unspecified', name='obligationowner', create_type=False), nullable=True, server_default='unspecified'))
    op.add_column('obligations', sa.Column('category', postgresql.ENUM('service_provision', 'service_levels', 'delivery', 'performance', 'payment', 'invoicing', 'pricing', 'data_protection', 'data_handling', 'reporting', 'information_provision', 'record_keeping', 'regulatory_compliance', 'audit', 'certification', 'insurance', 'confidentiality', 'ip_protection', 'notification', 'approval', 'cooperation', 'staffing', 'training', 'documentation', 'maintenance', 'support', 'testing', 'quality_assurance', 'transition', 'exit_management', 'return_of_materials', 'branding', 'marketing', 'collaboration', 'other', name='obligationcategory', create_type=False), nullable=True))
    op.add_column('obligations', sa.Column('frequency', postgresql.ENUM('one_time', 'daily', 'weekly', 'monthly', 'quarterly', 'semi_annual', 'annual', 'ongoing', 'triggered', 'as_needed', 'custom', name='obligationfrequency', create_type=False), nullable=True))
    op.add_column('obligations', sa.Column('frequency_custom', sa.String(100), nullable=True))
    op.add_column('obligations', sa.Column('rag_status', postgresql.ENUM('green', 'amber', 'red', 'not_assessed', name='ragstatus', create_type=False), nullable=True, server_default='not_assessed'))
    op.add_column('obligations', sa.Column('last_compliance_check', sa.DateTime(timezone=True), nullable=True))
    op.add_column('obligations', sa.Column('last_compliance_date', sa.Date(), nullable=True))
    op.add_column('obligations', sa.Column('next_compliance_due', sa.Date(), nullable=True))
    op.add_column('obligations', sa.Column('compliance_notes', sa.Text(), nullable=True))
    op.add_column('obligations', sa.Column('compliance_evidence', sa.Text(), nullable=True))
    op.add_column('obligations', sa.Column('is_critical', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('obligations', sa.Column('priority', sa.Integer(), nullable=True))
    op.add_column('obligations', sa.Column('section_reference', sa.String(100), nullable=True))

    # Create indexes for new obligation columns
    op.create_index('ix_obligations_owner_category', 'obligations', ['owner_type', 'category'])
    op.create_index('ix_obligations_rag_status', 'obligations', ['rag_status'])
    op.create_index('ix_obligations_next_compliance', 'obligations', ['next_compliance_due'])


def downgrade() -> None:
    """Remove canonical tables and obligation fields."""

    # Drop indexes on obligations
    op.drop_index('ix_obligations_next_compliance', table_name='obligations')
    op.drop_index('ix_obligations_rag_status', table_name='obligations')
    op.drop_index('ix_obligations_owner_category', table_name='obligations')

    # Drop new columns from obligations
    op.drop_column('obligations', 'section_reference')
    op.drop_column('obligations', 'priority')
    op.drop_column('obligations', 'is_critical')
    op.drop_column('obligations', 'compliance_evidence')
    op.drop_column('obligations', 'compliance_notes')
    op.drop_column('obligations', 'next_compliance_due')
    op.drop_column('obligations', 'last_compliance_date')
    op.drop_column('obligations', 'last_compliance_check')
    op.drop_column('obligations', 'rag_status')
    op.drop_column('obligations', 'frequency_custom')
    op.drop_column('obligations', 'frequency')
    op.drop_column('obligations', 'category')
    op.drop_column('obligations', 'owner_type')

    # Drop tables
    op.drop_table('contract_links')
    op.drop_table('contract_clause_indicators')
    op.drop_table('contract_liabilities')
    op.drop_table('contract_financials')

    # Drop enum types
    op.execute("DROP TYPE ragstatus")
    op.execute("DROP TYPE obligationfrequency")
    op.execute("DROP TYPE obligationcategory")
    op.execute("DROP TYPE obligationowner")
    op.execute("DROP TYPE linktype")
    op.execute("DROP TYPE liabilitycaptype")
    op.execute("DROP TYPE penaltytype")
    op.execute("DROP TYPE paymentterms")
    op.execute("DROP TYPE feetype")
