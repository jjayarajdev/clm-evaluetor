"""Add organization hierarchy and officers

Revision ID: fg02_orghierarchy
Revises: fg01_svcportfolio
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fg02_orghierarchy'
down_revision: Union[str, None] = 'fg01_svcportfolio'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enum types ---
    op.execute(
        "CREATE TYPE organizationlevel AS ENUM "
        "('holding', 'subsidiary', 'division', 'branch', 'department')"
    )
    op.execute(
        "CREATE TYPE governance_role_type AS ENUM "
        "('account_manager', 'service_delivery_manager', 'relationship_owner', "
        "'executive_sponsor', 'commercial_manager', 'technical_lead', "
        "'operations_lead', 'compliance_officer', 'other')"
    )
    op.execute(
        "CREATE TYPE officer_side AS ENUM ('internal', 'external')"
    )

    # --- Organization hierarchy columns ---
    op.add_column(
        'organizations',
        sa.Column(
            'parent_organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organizations.id'),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_organizations_parent_organization_id',
        'organizations',
        ['parent_organization_id'],
    )
    op.add_column(
        'organizations',
        sa.Column(
            'organization_level',
            postgresql.ENUM(
                'holding', 'subsidiary', 'division', 'branch', 'department',
                name='organizationlevel',
                create_type=False,
            ),
            nullable=True,
        ),
    )

    # --- Organization officers table ---
    op.create_table(
        'organization_officers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'tenant_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('tenants.id'),
            nullable=False,
        ),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organizations.id'),
            nullable=False,
        ),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column(
            'governance_role',
            postgresql.ENUM(
                'account_manager', 'service_delivery_manager', 'relationship_owner',
                'executive_sponsor', 'commercial_manager', 'technical_lead',
                'operations_lead', 'compliance_officer', 'other',
                name='governance_role_type',
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            'side',
            postgresql.ENUM(
                'internal', 'external',
                name='officer_side',
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        'ix_organization_officers_tenant_id',
        'organization_officers',
        ['tenant_id'],
    )
    op.create_index(
        'ix_organization_officers_organization_id',
        'organization_officers',
        ['organization_id'],
    )


def downgrade() -> None:
    # Drop officers table and indexes
    op.drop_index('ix_organization_officers_organization_id', table_name='organization_officers')
    op.drop_index('ix_organization_officers_tenant_id', table_name='organization_officers')
    op.drop_table('organization_officers')

    # Drop hierarchy columns
    op.drop_column('organizations', 'organization_level')
    op.drop_index('ix_organizations_parent_organization_id', table_name='organizations')
    op.drop_column('organizations', 'parent_organization_id')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS officer_side")
    op.execute("DROP TYPE IF EXISTS governance_role_type")
    op.execute("DROP TYPE IF EXISTS organizationlevel")
