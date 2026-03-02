"""Add business unit hierarchy and external user access

Revision ID: x7y8z9a0b1c2
Revises: w6x7y8z9a0b1
Create Date: 2026-03-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'x7y8z9a0b1c2'
down_revision: Union[str, None] = 'w6x7y8z9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add BU_HEAD to Role enum
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'bu_head'")

    # Add CONTRACT_ACCESS to TokenType enum
    op.execute("ALTER TYPE tokentype ADD VALUE IF NOT EXISTS 'contract_access'")

    # Create business_units table
    op.create_table(
        'business_units',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_units.id'), nullable=True),
        sa.Column('head_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_business_units_tenant_code'),
    )
    op.create_index('ix_business_units_tenant', 'business_units', ['tenant_id'])
    op.create_index('ix_business_units_parent', 'business_units', ['parent_id'])

    # Add business_unit_id to users table
    op.add_column('users', sa.Column('business_unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_units.id'), nullable=True))
    op.create_index('ix_users_business_unit', 'users', ['business_unit_id'])

    # Add business_unit_id to contracts table
    op.add_column('contracts', sa.Column('business_unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('business_units.id'), nullable=True))
    op.create_index('ix_contracts_business_unit', 'contracts', ['business_unit_id'])

    # Create external_users table
    op.create_table(
        'external_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('title', sa.String(100), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('invited_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('invited_at', sa.DateTime(), nullable=True),
        sa.Column('last_access_at', sa.DateTime(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_external_users_tenant_email'),
    )
    op.create_index('ix_external_users_tenant', 'external_users', ['tenant_id'])
    op.create_index('ix_external_users_email', 'external_users', ['email'])
    op.create_index('ix_external_users_organization', 'external_users', ['organization_id'])

    # Create contract_shares table
    op.create_table(
        'contract_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('external_users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('can_download', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_comment', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_access_at', sa.DateTime(), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('contract_id', 'external_user_id', name='uq_contract_shares_contract_user'),
    )
    op.create_index('ix_contract_shares_contract', 'contract_shares', ['contract_id'])
    op.create_index('ix_contract_shares_external_user', 'contract_shares', ['external_user_id'])

    # Create contract_comments table
    op.create_table(
        'contract_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('external_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('external_users.id'), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contract_comments.id'), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('clause_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clauses.id'), nullable=True),
        sa.Column('section_reference', sa.String(100), nullable=True),
        sa.Column('is_internal', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.CheckConstraint(
            '(user_id IS NOT NULL AND external_user_id IS NULL) OR (user_id IS NULL AND external_user_id IS NOT NULL)',
            name='ck_contract_comments_author'
        ),
    )
    op.create_index('ix_contract_comments_contract', 'contract_comments', ['contract_id'])
    op.create_index('ix_contract_comments_user', 'contract_comments', ['user_id'])
    op.create_index('ix_contract_comments_external_user', 'contract_comments', ['external_user_id'])
    op.create_index('ix_contract_comments_parent', 'contract_comments', ['parent_id'])
    op.create_index('ix_contract_comments_clause', 'contract_comments', ['clause_id'])

    # Add columns to external_access_tokens for contract access
    op.add_column('external_access_tokens', sa.Column('external_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('external_users.id'), nullable=True))
    op.add_column('external_access_tokens', sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id'), nullable=True))
    op.create_index('ix_external_access_tokens_external_user', 'external_access_tokens', ['external_user_id'])
    op.create_index('ix_external_access_tokens_contract', 'external_access_tokens', ['contract_id'])

    # Add tenant_id to organizations if not exists (for consistency)
    # This is already present from previous migration, so we just create an index
    op.create_index('ix_organizations_tenant', 'organizations', ['tenant_id'])


def downgrade() -> None:
    # Drop index on organizations
    op.drop_index('ix_organizations_tenant', table_name='organizations')

    # Drop columns from external_access_tokens
    op.drop_index('ix_external_access_tokens_contract', table_name='external_access_tokens')
    op.drop_index('ix_external_access_tokens_external_user', table_name='external_access_tokens')
    op.drop_column('external_access_tokens', 'contract_id')
    op.drop_column('external_access_tokens', 'external_user_id')

    # Drop contract_comments table
    op.drop_index('ix_contract_comments_clause', table_name='contract_comments')
    op.drop_index('ix_contract_comments_parent', table_name='contract_comments')
    op.drop_index('ix_contract_comments_external_user', table_name='contract_comments')
    op.drop_index('ix_contract_comments_user', table_name='contract_comments')
    op.drop_index('ix_contract_comments_contract', table_name='contract_comments')
    op.drop_table('contract_comments')

    # Drop contract_shares table
    op.drop_index('ix_contract_shares_external_user', table_name='contract_shares')
    op.drop_index('ix_contract_shares_contract', table_name='contract_shares')
    op.drop_table('contract_shares')

    # Drop external_users table
    op.drop_index('ix_external_users_organization', table_name='external_users')
    op.drop_index('ix_external_users_email', table_name='external_users')
    op.drop_index('ix_external_users_tenant', table_name='external_users')
    op.drop_table('external_users')

    # Drop business_unit_id from contracts
    op.drop_index('ix_contracts_business_unit', table_name='contracts')
    op.drop_column('contracts', 'business_unit_id')

    # Drop business_unit_id from users
    op.drop_index('ix_users_business_unit', table_name='users')
    op.drop_column('users', 'business_unit_id')

    # Drop business_units table
    op.drop_index('ix_business_units_parent', table_name='business_units')
    op.drop_index('ix_business_units_tenant', table_name='business_units')
    op.drop_table('business_units')

    # Note: Cannot remove enum values in PostgreSQL easily
    # The bu_head and contract_access values will remain
