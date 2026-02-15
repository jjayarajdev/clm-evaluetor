"""Add SLA benchmark fields for IT outsourcing contracts

Revision ID: j3k4l5m6n7o8
Revises: i2j3k4l5m6n7
Create Date: 2026-02-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j3k4l5m6n7o8'
down_revision: Union[str, Sequence[str], None] = 'i2j3k4l5m6n7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new columns to contract_slas for IT outsourcing contracts."""
    # Section reference from contract
    op.add_column(
        'contract_slas',
        sa.Column('section_reference', sa.String(50), nullable=True)
    )

    # Category (Critical Service Levels, Key Measurements, etc.)
    op.add_column(
        'contract_slas',
        sa.Column('category', sa.String(100), nullable=True)
    )

    # Service tower (Desktop Services, Network Services, etc.)
    op.add_column(
        'contract_slas',
        sa.Column('service_tower', sa.String(100), nullable=True)
    )

    # At-risk pool percentage allocation
    op.add_column(
        'contract_slas',
        sa.Column('at_risk_percentage', sa.Numeric(5, 2), nullable=True)
    )

    # Earnback eligibility
    op.add_column(
        'contract_slas',
        sa.Column('earnback_eligible', sa.Boolean(), server_default='false', nullable=False)
    )

    # Earnback conditions text
    op.add_column(
        'contract_slas',
        sa.Column('earnback_conditions', sa.Text(), nullable=True)
    )

    # Minimum service level (floor/default threshold)
    op.add_column(
        'contract_slas',
        sa.Column('minimum_service_level', sa.Numeric(10, 4), nullable=True)
    )

    # Add index for section reference lookups
    op.create_index(
        'ix_sla_section_ref',
        'contract_slas',
        ['contract_id', 'section_reference']
    )


def downgrade() -> None:
    """Remove the added columns."""
    op.drop_index('ix_sla_section_ref', table_name='contract_slas')

    op.drop_column('contract_slas', 'minimum_service_level')
    op.drop_column('contract_slas', 'earnback_conditions')
    op.drop_column('contract_slas', 'earnback_eligible')
    op.drop_column('contract_slas', 'at_risk_percentage')
    op.drop_column('contract_slas', 'service_tower')
    op.drop_column('contract_slas', 'category')
    op.drop_column('contract_slas', 'section_reference')
