"""Add contract documents, signatures, and sections tables

Revision ID: fg03_contractdocs
Revises: fg02_orghierarchy
Create Date: 2026-03-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fg03_contractdocs'
down_revision: Union[str, None] = 'fg02_orghierarchy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        CREATE TYPE documenttype AS ENUM (
            'main_agreement', 'amendment', 'addendum', 'schedule', 'exhibit',
            'statement_of_work', 'side_letter', 'appendix', 'certificate', 'other'
        )
    """)
    op.execute("""
        CREATE TYPE signaturetype AS ENUM (
            'wet_ink', 'digital', 'electronic', 'stamp'
        )
    """)
    op.execute("""
        CREATE TYPE signaturestatus AS ENUM (
            'pending', 'signed', 'declined', 'expired'
        )
    """)

    # Create contract_documents table
    op.create_table(
        'contract_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_type', postgresql.ENUM('main_agreement', 'amendment', 'addendum', 'schedule', 'exhibit', 'statement_of_work', 'side_letter', 'appendix', 'certificate', 'other', name='documenttype', create_type=False), nullable=False, server_default='other'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('version', sa.String(20), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('upload_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_contract_documents_tenant', 'contract_documents', ['tenant_id'])
    op.create_index('ix_contract_documents_contract', 'contract_documents', ['contract_id'])
    op.create_index('ix_contract_documents_type', 'contract_documents', ['document_type'])

    # Create document_signatures table
    op.create_table(
        'document_signatures',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contract_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('signer_name', sa.String(255), nullable=False),
        sa.Column('signer_title', sa.String(255), nullable=True),
        sa.Column('signer_organization', sa.String(255), nullable=True),
        sa.Column('signer_email', sa.String(255), nullable=True),
        sa.Column('signed_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('signature_type', postgresql.ENUM('wet_ink', 'digital', 'electronic', 'stamp', name='signaturetype', create_type=False), nullable=False, server_default='electronic'),
        sa.Column('signature_status', postgresql.ENUM('pending', 'signed', 'declined', 'expired', name='signaturestatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_document_signatures_document', 'document_signatures', ['document_id'])

    # Create document_sections table
    op.create_table(
        'document_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contract_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_section_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('document_sections.id', ondelete='CASCADE'), nullable=True),
        sa.Column('section_number', sa.String(50), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content_summary', sa.Text(), nullable=True),
        sa.Column('page_start', sa.Integer(), nullable=True),
        sa.Column('page_end', sa.Integer(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_document_sections_document', 'document_sections', ['document_id'])
    op.create_index('ix_document_sections_parent', 'document_sections', ['parent_section_id'])


def downgrade() -> None:
    # Drop tables in reverse order of creation (child tables first)
    op.drop_index('ix_document_sections_parent', table_name='document_sections')
    op.drop_index('ix_document_sections_document', table_name='document_sections')
    op.drop_table('document_sections')

    op.drop_index('ix_document_signatures_document', table_name='document_signatures')
    op.drop_table('document_signatures')

    op.drop_index('ix_contract_documents_type', table_name='contract_documents')
    op.drop_index('ix_contract_documents_contract', table_name='contract_documents')
    op.drop_index('ix_contract_documents_tenant', table_name='contract_documents')
    op.drop_table('contract_documents')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS signaturestatus")
    op.execute("DROP TYPE IF EXISTS signaturetype")
    op.execute("DROP TYPE IF EXISTS documenttype")
