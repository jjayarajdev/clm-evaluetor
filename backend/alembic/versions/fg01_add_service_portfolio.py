"""Add service portfolio tables.

Revision ID: fg01_svcportfolio
Revises: z9a0b1c2d3e4
Create Date: 2026-03-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'fg01_svcportfolio'
down_revision: Union[str, None] = 'z9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create servicetype enum (only if not exists)
    result = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'servicetype'"))
    if result.fetchone() is None:
        op.execute("""
            CREATE TYPE servicetype AS ENUM (
                'it_services', 'consulting', 'legal', 'financial', 'logistics',
                'manufacturing', 'marketing', 'hr', 'procurement', 'other'
            )
        """)

    # Create servicestatus enum (only if not exists)
    result = conn.execute(text("SELECT 1 FROM pg_type WHERE typname = 'servicestatus'"))
    if result.fetchone() is None:
        op.execute("""
            CREATE TYPE servicestatus AS ENUM (
                'active', 'inactive', 'planned', 'deprecated'
            )
        """)

    # Create service_portfolios table
    servicetype = postgresql.ENUM(
        'it_services', 'consulting', 'legal', 'financial', 'logistics',
        'manufacturing', 'marketing', 'hr', 'procurement', 'other',
        name='servicetype', create_type=False,
    )
    servicestatus = postgresql.ENUM(
        'active', 'inactive', 'planned', 'deprecated',
        name='servicestatus', create_type=False,
    )

    op.create_table(
        'service_portfolios',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('service_type', servicetype, nullable=False, server_default='other'),
        sa.Column('status', servicestatus, nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )

    # Create indexes for service_portfolios
    op.create_index('ix_service_portfolios_tenant_id', 'service_portfolios', ['tenant_id'])
    op.create_index('ix_service_portfolios_organization_id', 'service_portfolios', ['organization_id'])
    op.create_index('ix_service_portfolios_service_type', 'service_portfolios', ['service_type'])
    op.create_index('ix_service_portfolios_status', 'service_portfolios', ['status'])
    # Unique code within tenant
    op.create_index(
        'ix_service_portfolios_tenant_code',
        'service_portfolios',
        ['tenant_id', 'code'],
        unique=True,
    )

    # Create relationship_services table
    op.create_table(
        'relationship_services',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('relationship_id', sa.UUID(), nullable=False),
        sa.Column('service_portfolio_id', sa.UUID(), nullable=False),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['relationship_id'], ['business_relationships.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['service_portfolio_id'], ['service_portfolios.id'], ondelete='CASCADE'
        ),
    )

    # Create indexes for relationship_services
    op.create_index('ix_relationship_services_relationship_id', 'relationship_services', ['relationship_id'])
    op.create_index('ix_relationship_services_service_portfolio_id', 'relationship_services', ['service_portfolio_id'])
    # Unique constraint: one service per relationship
    op.create_index(
        'ix_relationship_services_unique',
        'relationship_services',
        ['relationship_id', 'service_portfolio_id'],
        unique=True,
    )


def downgrade() -> None:
    # Drop relationship_services
    op.drop_index('ix_relationship_services_unique', 'relationship_services')
    op.drop_index('ix_relationship_services_service_portfolio_id', 'relationship_services')
    op.drop_index('ix_relationship_services_relationship_id', 'relationship_services')
    op.drop_table('relationship_services')

    # Drop service_portfolios
    op.drop_index('ix_service_portfolios_tenant_code', 'service_portfolios')
    op.drop_index('ix_service_portfolios_status', 'service_portfolios')
    op.drop_index('ix_service_portfolios_service_type', 'service_portfolios')
    op.drop_index('ix_service_portfolios_organization_id', 'service_portfolios')
    op.drop_index('ix_service_portfolios_tenant_id', 'service_portfolios')
    op.drop_table('service_portfolios')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS servicestatus")
    op.execute("DROP TYPE IF EXISTS servicetype")
