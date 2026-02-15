"""Add client model and contract versioning

Revision ID: 92b4d0a15c40
Revises:
Create Date: 2026-02-11 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '92b4d0a15c40'
down_revision: Union[str, None] = 'b1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('contact_title', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('ix_clients_code', 'clients', ['code'], unique=True)
    op.create_index('ix_clients_name', 'clients', ['name'], unique=False)

    # Add columns to contracts table
    op.add_column('contracts', sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('contracts', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('contracts', sa.Column('previous_version_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Create indexes and foreign keys
    op.create_index('ix_contracts_client_id', 'contracts', ['client_id'], unique=False)
    op.create_foreign_key('fk_contracts_client_id', 'contracts', 'clients', ['client_id'], ['id'])
    op.create_foreign_key('fk_contracts_previous_version', 'contracts', 'contracts', ['previous_version_id'], ['id'])


def downgrade() -> None:
    # Drop foreign keys and indexes
    op.drop_constraint('fk_contracts_previous_version', 'contracts', type_='foreignkey')
    op.drop_constraint('fk_contracts_client_id', 'contracts', type_='foreignkey')
    op.drop_index('ix_contracts_client_id', table_name='contracts')

    # Drop columns from contracts
    op.drop_column('contracts', 'previous_version_id')
    op.drop_column('contracts', 'version')
    op.drop_column('contracts', 'client_id')

    # Drop clients table
    op.drop_index('ix_clients_name', table_name='clients')
    op.drop_index('ix_clients_code', table_name='clients')
    op.drop_table('clients')
