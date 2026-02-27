"""Add industry-aware compliance module

Revision ID: r1s2t3u4v5w6
Revises: q0r1s2t3u4v5
Create Date: 2026-02-22

This migration adds:
- Industry enum for contract industry classification
- ComplianceDocumentType enum for required document types
- ComplianceGapSeverity and ComplianceGapStatus enums
- RegulationType and RegulatoryObligationCategory enums
- industry_compliance_rules table for defining required documents per industry
- compliance_gaps table for tracking missing compliance documents
- regulatory_obligations table for tracking regulatory requirements
- New fields on contracts table: detected_industry, industry_confidence, compliance_score, last_compliance_check
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

# revision identifiers, used by Alembic.
revision: str = 'r1s2t3u4v5w6'
down_revision: Union[str, None] = 'q0r1s2t3u4v5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===== CREATE ENUM TYPES =====

    # Industry enum
    op.execute("""
        CREATE TYPE industry AS ENUM (
            'pharmaceutical', 'healthcare', 'chemical', 'manufacturing',
            'technology', 'financial_services', 'energy', 'aerospace_defense',
            'food_beverage', 'automotive', 'telecommunications', 'retail',
            'construction', 'professional_services', 'other'
        )
    """)

    # ComplianceDocumentType enum
    op.execute("""
        CREATE TYPE compliancedocumenttype AS ENUM (
            'quality_agreement', 'pharmacovigilance_agreement', 'technical_agreement',
            'safety_data_exchange_agreement', 'baa', 'dpa', 'scc',
            'product_specifications', 'quality_management_plan', 'supplier_quality_agreement',
            'safety_data_sheet', 'environmental_compliance_plan',
            'security_addendum', 'soc2_report', 'penetration_test_report',
            'outsourcing_agreement', 'bcdr_plan',
            'insurance_certificate', 'audit_report', 'compliance_certification'
        )
    """)

    # ComplianceGapSeverity enum
    op.execute("""
        CREATE TYPE compliancegapseverity AS ENUM (
            'critical', 'high', 'medium', 'low'
        )
    """)

    # ComplianceGapStatus enum
    op.execute("""
        CREATE TYPE compliancegapstatus AS ENUM (
            'open', 'in_progress', 'pending_review', 'resolved', 'waived', 'not_applicable'
        )
    """)

    # RegulationType enum
    op.execute("""
        CREATE TYPE regulationtype AS ENUM (
            'fda', 'hipaa', 'epa', 'osha', 'sox', 'finra', 'sec', 'ftc',
            'gdpr', 'mdr', 'ivdr', 'reach',
            'gmp', 'gcp', 'glp', 'iso_9001', 'iso_13485', 'iso_27001', 'soc2', 'pci_dss',
            'ich', 'who', 'other'
        )
    """)

    # RegulatoryObligationCategory enum
    op.execute("""
        CREATE TYPE regulatoryobligationcategory AS ENUM (
            'audit_rights', 'change_control', 'deviation_reporting', 'corrective_action', 'quality_review',
            'recall_response', 'adverse_event_reporting', 'safety_monitoring', 'risk_assessment',
            'record_retention', 'documentation_control', 'batch_records', 'validation_records',
            'training_requirements', 'qualification_requirements',
            'regulatory_reporting', 'periodic_reporting', 'notification_requirements',
            'data_protection', 'breach_notification', 'data_retention',
            'environmental_compliance', 'waste_management', 'other'
        )
    """)

    # ===== ADD COLUMNS TO CONTRACTS =====

    industry_enum = ENUM(
        'pharmaceutical', 'healthcare', 'chemical', 'manufacturing',
        'technology', 'financial_services', 'energy', 'aerospace_defense',
        'food_beverage', 'automotive', 'telecommunications', 'retail',
        'construction', 'professional_services', 'other',
        name='industry', create_type=False
    )

    op.add_column('contracts', sa.Column('detected_industry', industry_enum, nullable=True))
    op.add_column('contracts', sa.Column('industry_confidence', sa.Float(), nullable=True))
    op.add_column('contracts', sa.Column('compliance_score', sa.Integer(), nullable=True))
    op.add_column('contracts', sa.Column('last_compliance_check', sa.DateTime(timezone=True), nullable=True))

    op.create_index('ix_contracts_detected_industry', 'contracts', ['detected_industry'])
    op.create_index('ix_contracts_industry_compliance', 'contracts', ['detected_industry', 'compliance_score'])

    # ===== CREATE INDUSTRY_COMPLIANCE_RULES TABLE =====

    compliancedocumenttype_enum = ENUM(
        'quality_agreement', 'pharmacovigilance_agreement', 'technical_agreement',
        'safety_data_exchange_agreement', 'baa', 'dpa', 'scc',
        'product_specifications', 'quality_management_plan', 'supplier_quality_agreement',
        'safety_data_sheet', 'environmental_compliance_plan',
        'security_addendum', 'soc2_report', 'penetration_test_report',
        'outsourcing_agreement', 'bcdr_plan',
        'insurance_certificate', 'audit_report', 'compliance_certification',
        name='compliancedocumenttype', create_type=False
    )

    compliancegapseverity_enum = ENUM(
        'critical', 'high', 'medium', 'low',
        name='compliancegapseverity', create_type=False
    )

    compliancegapstatus_enum = ENUM(
        'open', 'in_progress', 'pending_review', 'resolved', 'waived', 'not_applicable',
        name='compliancegapstatus', create_type=False
    )

    contracttype_enum = ENUM(
        'nda', 'msa', 'sow', 'amendment', 'vendor_agreement', 'employment_contract',
        name='contracttype', create_type=False
    )

    op.create_table(
        'industry_compliance_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),

        # Industry and contract type
        sa.Column('industry', industry_enum, nullable=False),
        sa.Column('primary_contract_type', contracttype_enum, nullable=False),

        # Required document
        sa.Column('required_document_type', compliancedocumenttype_enum, nullable=False),

        # Requirement details
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('condition_description', sa.Text(), nullable=True),

        # Severity and regulatory info
        sa.Column('severity_if_missing', compliancegapseverity_enum, nullable=False, server_default='medium'),
        sa.Column('regulatory_reference', sa.String(500), nullable=True),

        # Rule metadata
        sa.Column('rule_name', sa.String(255), nullable=False),
        sa.Column('rule_description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_industry_compliance_rules_industry', 'industry_compliance_rules', ['industry'])
    op.create_index('ix_industry_compliance_rules_contract_type', 'industry_compliance_rules', ['primary_contract_type'])
    op.create_index('ix_industry_compliance_rules_document_type', 'industry_compliance_rules', ['required_document_type'])
    op.create_index('ix_compliance_rules_industry_contract', 'industry_compliance_rules', ['industry', 'primary_contract_type'])
    op.create_index('ix_compliance_rules_active_industry', 'industry_compliance_rules', ['is_active', 'industry'])

    # ===== CREATE COMPLIANCE_GAPS TABLE =====

    op.create_table(
        'compliance_gaps',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),

        # Related contract
        sa.Column('contract_id', UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),

        # Rule reference
        sa.Column('rule_id', UUID(as_uuid=True), sa.ForeignKey('industry_compliance_rules.id', ondelete='SET NULL'), nullable=True),

        # Gap details
        sa.Column('missing_document_type', compliancedocumenttype_enum, nullable=False),
        sa.Column('gap_description', sa.Text(), nullable=False),
        sa.Column('regulatory_reference', sa.String(500), nullable=True),

        # Severity and status
        sa.Column('severity', compliancegapseverity_enum, nullable=False, server_default='medium'),
        sa.Column('status', compliancegapstatus_enum, nullable=False, server_default='open'),

        # Resolution tracking
        sa.Column('resolution_due_date', sa.Date(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),

        # Linked document
        sa.Column('linked_document_id', UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='SET NULL'), nullable=True),

        # Detection metadata
        sa.Column('detection_confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('detection_reasoning', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),

        # Waiver information
        sa.Column('waiver_reason', sa.Text(), nullable=True),
        sa.Column('waiver_approved_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('waiver_approved_at', sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_compliance_gaps_contract_id', 'compliance_gaps', ['contract_id'])
    op.create_index('ix_compliance_gaps_rule_id', 'compliance_gaps', ['rule_id'])
    op.create_index('ix_compliance_gaps_document_type', 'compliance_gaps', ['missing_document_type'])
    op.create_index('ix_compliance_gaps_severity', 'compliance_gaps', ['severity'])
    op.create_index('ix_compliance_gaps_status', 'compliance_gaps', ['status'])
    op.create_index('ix_compliance_gaps_due_date', 'compliance_gaps', ['resolution_due_date'])
    op.create_index('ix_compliance_gaps_contract_status', 'compliance_gaps', ['contract_id', 'status'])
    op.create_index('ix_compliance_gaps_severity_status', 'compliance_gaps', ['severity', 'status'])
    op.create_index('ix_compliance_gaps_linked_document', 'compliance_gaps', ['linked_document_id'])

    # ===== CREATE REGULATORY_OBLIGATIONS TABLE =====

    regulationtype_enum = ENUM(
        'fda', 'hipaa', 'epa', 'osha', 'sox', 'finra', 'sec', 'ftc',
        'gdpr', 'mdr', 'ivdr', 'reach',
        'gmp', 'gcp', 'glp', 'iso_9001', 'iso_13485', 'iso_27001', 'soc2', 'pci_dss',
        'ich', 'who', 'other',
        name='regulationtype', create_type=False
    )

    regulatoryobligationcategory_enum = ENUM(
        'audit_rights', 'change_control', 'deviation_reporting', 'corrective_action', 'quality_review',
        'recall_response', 'adverse_event_reporting', 'safety_monitoring', 'risk_assessment',
        'record_retention', 'documentation_control', 'batch_records', 'validation_records',
        'training_requirements', 'qualification_requirements',
        'regulatory_reporting', 'periodic_reporting', 'notification_requirements',
        'data_protection', 'breach_notification', 'data_retention',
        'environmental_compliance', 'waste_management', 'other',
        name='regulatoryobligationcategory', create_type=False
    )

    ragstatus_enum = ENUM(
        'green', 'amber', 'red', 'not_assessed',
        name='ragstatus', create_type=False
    )

    op.create_table(
        'regulatory_obligations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),

        # Related contract
        sa.Column('contract_id', UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),

        # Industry and regulation
        sa.Column('industry', industry_enum, nullable=False),
        sa.Column('regulation_type', regulationtype_enum, nullable=False),
        sa.Column('regulation_reference', sa.String(255), nullable=True),

        # Obligation details
        sa.Column('obligation_category', regulatoryobligationcategory_enum, nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('source_section', sa.String(100), nullable=True),

        # Responsible party
        sa.Column('responsible_party', sa.String(255), nullable=True),

        # Frequency and timing
        sa.Column('frequency', sa.String(50), nullable=True),
        sa.Column('next_due_date', sa.Date(), nullable=True),
        sa.Column('last_completed_date', sa.Date(), nullable=True),

        # Compliance tracking
        sa.Column('compliance_status', ragstatus_enum, nullable=False, server_default='not_assessed'),
        sa.Column('last_compliance_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('compliance_notes', sa.Text(), nullable=True),
        sa.Column('compliance_evidence', sa.Text(), nullable=True),

        # Extraction metadata
        sa.Column('extraction_confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('extraction_metadata', JSONB(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index('ix_regulatory_obligations_contract_id', 'regulatory_obligations', ['contract_id'])
    op.create_index('ix_regulatory_obligations_industry', 'regulatory_obligations', ['industry'])
    op.create_index('ix_regulatory_obligations_regulation_type', 'regulatory_obligations', ['regulation_type'])
    op.create_index('ix_regulatory_obligations_category', 'regulatory_obligations', ['obligation_category'])
    op.create_index('ix_regulatory_obligations_status', 'regulatory_obligations', ['compliance_status'])
    op.create_index('ix_regulatory_obligations_due_date', 'regulatory_obligations', ['next_due_date'])
    op.create_index('ix_regulatory_obligations_contract_status', 'regulatory_obligations', ['contract_id', 'compliance_status'])
    op.create_index('ix_regulatory_obligations_regulation', 'regulatory_obligations', ['regulation_type', 'obligation_category'])
    op.create_index('ix_regulatory_obligations_due_date_status', 'regulatory_obligations', ['next_due_date', 'compliance_status'])
    op.create_index('ix_regulatory_obligations_industry_regulation', 'regulatory_obligations', ['industry', 'regulation_type'])


def downgrade() -> None:
    # Drop indexes and tables

    # Regulatory obligations
    op.drop_index('ix_regulatory_obligations_industry_regulation', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_due_date_status', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_regulation', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_contract_status', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_due_date', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_status', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_category', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_regulation_type', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_industry', table_name='regulatory_obligations')
    op.drop_index('ix_regulatory_obligations_contract_id', table_name='regulatory_obligations')
    op.drop_table('regulatory_obligations')

    # Compliance gaps
    op.drop_index('ix_compliance_gaps_linked_document', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_severity_status', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_contract_status', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_due_date', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_status', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_severity', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_document_type', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_rule_id', table_name='compliance_gaps')
    op.drop_index('ix_compliance_gaps_contract_id', table_name='compliance_gaps')
    op.drop_table('compliance_gaps')

    # Industry compliance rules
    op.drop_index('ix_compliance_rules_active_industry', table_name='industry_compliance_rules')
    op.drop_index('ix_compliance_rules_industry_contract', table_name='industry_compliance_rules')
    op.drop_index('ix_industry_compliance_rules_document_type', table_name='industry_compliance_rules')
    op.drop_index('ix_industry_compliance_rules_contract_type', table_name='industry_compliance_rules')
    op.drop_index('ix_industry_compliance_rules_industry', table_name='industry_compliance_rules')
    op.drop_table('industry_compliance_rules')

    # Drop columns from contracts
    op.drop_index('ix_contracts_industry_compliance', table_name='contracts')
    op.drop_index('ix_contracts_detected_industry', table_name='contracts')
    op.drop_column('contracts', 'last_compliance_check')
    op.drop_column('contracts', 'compliance_score')
    op.drop_column('contracts', 'industry_confidence')
    op.drop_column('contracts', 'detected_industry')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS regulatoryobligationcategory")
    op.execute("DROP TYPE IF EXISTS regulationtype")
    op.execute("DROP TYPE IF EXISTS compliancegapstatus")
    op.execute("DROP TYPE IF EXISTS compliancegapseverity")
    op.execute("DROP TYPE IF EXISTS compliancedocumenttype")
    op.execute("DROP TYPE IF EXISTS industry")
