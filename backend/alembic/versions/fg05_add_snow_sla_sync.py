"""Add ServiceNow SLA sync support - tenant_id on integration_configs + snow_sla_mappings table

Revision ID: fg05_snowslasync
Revises: fg04_kpiapproval
Create Date: 2026-03-22 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'fg05_snowslasync'
down_revision: Union[str, None] = 'fg04_kpiapproval'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Add tenant_id to integration_configs ===
    op.add_column('integration_configs', sa.Column(
        'tenant_id',
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey('tenants.id'),
        nullable=True,  # nullable so existing rows work
    ))
    op.create_index('ix_integration_configs_tenant_id', 'integration_configs', ['tenant_id'])

    # === Create snow_sla_mappings table ===
    op.create_table(
        'snow_sla_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('integration_config_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('integration_configs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('snow_sys_id', sa.String(100), nullable=False),
        sa.Column('platform_sla_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('contract_slas.id', ondelete='CASCADE'), nullable=True),
        sa.Column('snow_sla_name', sa.String(500), nullable=True),
        sa.Column('snow_metric_type', sa.String(100), nullable=True),
        sa.Column('snow_target', sa.String(100), nullable=True),
        sa.Column('mapping_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('integration_config_id', 'snow_sys_id', name='uq_snow_sla_mapping_config_sysid'),
    )

    # Create indexes for common query patterns
    op.create_index('ix_snow_sla_mappings_tenant_id', 'snow_sla_mappings', ['tenant_id'])
    op.create_index('ix_snow_sla_mappings_integration_config_id', 'snow_sla_mappings', ['integration_config_id'])
    op.create_index('ix_snow_sla_mappings_platform_sla_id', 'snow_sla_mappings', ['platform_sla_id'])


def downgrade() -> None:
    # Drop snow_sla_mappings indexes and table
    op.drop_index('ix_snow_sla_mappings_platform_sla_id', table_name='snow_sla_mappings')
    op.drop_index('ix_snow_sla_mappings_integration_config_id', table_name='snow_sla_mappings')
    op.drop_index('ix_snow_sla_mappings_tenant_id', table_name='snow_sla_mappings')
    op.drop_table('snow_sla_mappings')

    # Drop tenant_id from integration_configs
    op.drop_index('ix_integration_configs_tenant_id', table_name='integration_configs')
    op.drop_column('integration_configs', 'tenant_id')
