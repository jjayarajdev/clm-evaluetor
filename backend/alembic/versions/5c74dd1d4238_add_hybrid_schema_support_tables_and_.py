"""Add hybrid schema support tables and columns

Revision ID: 5c74dd1d4238
Revises: 3b3f773d8f37
Create Date: 2026-02-01 11:28:29.063518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5c74dd1d4238'
down_revision: Union[str, Sequence[str], None] = '3b3f773d8f37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add hybrid schema support: promoted columns + child tables."""

    # Create enum types
    op.execute("CREATE TYPE partyrole AS ENUM ('provider', 'client', 'vendor', 'customer', 'licensor', 'licensee', 'employer', 'employee', 'disclosing_party', 'receiving_party', 'other')")
    op.execute("CREATE TYPE dateeventtype AS ENUM ('contract_start', 'contract_expiration', 'renewal_notice_deadline', 'termination_notice_deadline', 'payment_due', 'delivery_due', 'milestone', 'review_date', 'renewal_date', 'obligation_deadline', 'custom')")

    # Add promoted columns to contracts table
    op.add_column('contracts', sa.Column('governing_law', sa.String(200), nullable=True))
    op.add_column('contracts', sa.Column('initial_term_months', sa.Integer(), nullable=True))
    op.add_column('contracts', sa.Column('liability_cap_type', sa.String(50), nullable=True))
    op.add_column('contracts', sa.Column('liability_cap_amount', sa.Numeric(15, 2), nullable=True))
    op.add_column('contracts', sa.Column('dispute_resolution_method', sa.String(50), nullable=True))
    op.add_column('contracts', sa.Column('termination_for_convenience', sa.Boolean(), nullable=True))
    op.add_column('contracts', sa.Column('confidentiality_term_years', sa.Integer(), nullable=True))

    # Create contract_parties table
    op.create_table(
        'contract_parties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', postgresql.ENUM('provider', 'client', 'vendor', 'customer', 'licensor', 'licensee', 'employer', 'employee', 'disclosing_party', 'receiving_party', 'other', name='partyrole', create_type=False), nullable=False, server_default='other'),
        sa.Column('legal_name', sa.String(500), nullable=False),
        sa.Column('short_name', sa.String(100), nullable=True),
        sa.Column('entity_type', sa.String(100), nullable=True),
        sa.Column('jurisdiction', sa.String(200), nullable=True),
        sa.Column('registered_address', sa.Text(), nullable=True),
        sa.Column('contact_name', sa.String(255), nullable=True),
        sa.Column('contact_email', sa.String(255), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('section_reference', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_contract_parties_contract_id', 'contract_parties', ['contract_id'])
    op.create_index('ix_contract_parties_contract_role', 'contract_parties', ['contract_id', 'role'])
    op.create_index('ix_contract_parties_legal_name', 'contract_parties', ['legal_name'])

    # Create contract_key_dates table
    op.create_table(
        'contract_key_dates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', postgresql.ENUM('contract_start', 'contract_expiration', 'renewal_notice_deadline', 'termination_notice_deadline', 'payment_due', 'delivery_due', 'milestone', 'review_date', 'renewal_date', 'obligation_deadline', 'custom', name='dateeventtype', create_type=False), nullable=False),
        sa.Column('event_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('notice_required_by', sa.Date(), nullable=True),
        sa.Column('action_required', sa.Text(), nullable=True),
        sa.Column('responsible_party', sa.String(255), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('recurrence_pattern', sa.String(100), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('completed_date', sa.Date(), nullable=True),
        sa.Column('alert_days_before', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('alert_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('section_reference', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_contract_key_dates_contract_id', 'contract_key_dates', ['contract_id'])
    op.create_index('ix_key_dates_contract_event', 'contract_key_dates', ['contract_id', 'event_type'])
    op.create_index('ix_key_dates_upcoming', 'contract_key_dates', ['event_date', 'is_completed'])
    op.create_index('ix_key_dates_notice_deadline', 'contract_key_dates', ['notice_required_by', 'is_completed'])
    op.create_index('ix_key_dates_event_type', 'contract_key_dates', ['event_type'])


def downgrade() -> None:
    """Remove hybrid schema support."""

    # Drop tables
    op.drop_table('contract_key_dates')
    op.drop_table('contract_parties')

    # Drop promoted columns from contracts
    op.drop_column('contracts', 'confidentiality_term_years')
    op.drop_column('contracts', 'termination_for_convenience')
    op.drop_column('contracts', 'dispute_resolution_method')
    op.drop_column('contracts', 'liability_cap_amount')
    op.drop_column('contracts', 'liability_cap_type')
    op.drop_column('contracts', 'initial_term_months')
    op.drop_column('contracts', 'governing_law')

    # Drop enum types
    op.execute("DROP TYPE dateeventtype")
    op.execute("DROP TYPE partyrole")
