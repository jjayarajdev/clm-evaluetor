"""Add roles + role_permissions tables (DB-driven RBAC matrix).

No data seeding here — the startup seed in core/permissions.py is the single
code path (runs only when the roles table is empty).

Revision ID: rbacdb01
Revises: hiercache01
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'rbacdb01'
down_revision: Union[str, None] = 'hiercache01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'roles',
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('name'),
    )
    op.create_table(
        'role_permissions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('role_name', sa.String(50), nullable=False),
        sa.Column('permission', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['role_name'], ['roles.name'], ondelete='CASCADE'),
        sa.UniqueConstraint('role_name', 'permission', name='uq_role_permission'),
    )
    op.create_index('ix_role_permissions_role_name', 'role_permissions', ['role_name'])


def downgrade() -> None:
    op.drop_index('ix_role_permissions_role_name', table_name='role_permissions')
    op.drop_table('role_permissions')
    op.drop_table('roles')
