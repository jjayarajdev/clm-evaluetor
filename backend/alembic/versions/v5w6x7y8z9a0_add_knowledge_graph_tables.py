"""Add knowledge graph tables for contract entity extraction

Revision ID: v5w6x7y8z9a0
Revises: u4v5w6x7y8z9
Create Date: 2026-02-27 10:00:00.000000

This migration creates the kg_entities and kg_relationships tables
for storing extracted entities and their relationships from contracts.
This enables better entity resolution, cross-reference understanding,
and risk pattern detection.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'v5w6x7y8z9a0'
down_revision: Union[str, None] = 'u4v5w6x7y8z9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types for entity and relationship types
    op.execute("""
        CREATE TYPE kgentitytype AS ENUM (
            'party',
            'clause',
            'obligation',
            'term',
            'date',
            'amount',
            'jurisdiction',
            'sla_metric'
        )
    """)

    op.execute("""
        CREATE TYPE kgrelationshiptype AS ENUM (
            'has_party',
            'has_obligation',
            'benefits_from',
            'references',
            'limited_by',
            'defined_as',
            'triggered_by',
            'governed_by',
            'amends',
            'expires_on'
        )
    """)

    # Create kg_entities table (nodes in the knowledge graph)
    op.create_table(
        'kg_entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),

        # Entity identification
        sa.Column('entity_type', postgresql.ENUM(
            'party', 'clause', 'obligation', 'term', 'date', 'amount', 'jurisdiction', 'sla_metric',
            name='kgentitytype', create_type=False
        ), nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('normalized_name', sa.String(500), nullable=True),  # Lowercase for matching

        # Flexible attributes
        sa.Column('properties', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Source tracking
        sa.Column('source_text', sa.Text(), nullable=True),
        sa.Column('source_section', sa.String(50), nullable=True),
        sa.Column('source_page', sa.Integer(), nullable=True),

        # Confidence and metadata
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Indexes for efficient entity lookups
    op.create_index('ix_kg_entities_contract', 'kg_entities', ['contract_id'])
    op.create_index('ix_kg_entities_tenant', 'kg_entities', ['tenant_id'])
    op.create_index('ix_kg_entities_type', 'kg_entities', ['entity_type'])
    op.create_index('ix_kg_entities_normalized_name', 'kg_entities', ['normalized_name'])
    op.create_index('ix_kg_entities_contract_type', 'kg_entities', ['contract_id', 'entity_type'])

    # Create kg_relationships table (edges in the knowledge graph)
    op.create_table(
        'kg_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),

        # Relationship endpoints
        sa.Column('source_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kg_entities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('kg_entities.id', ondelete='CASCADE'), nullable=False),

        # Relationship type
        sa.Column('relationship_type', postgresql.ENUM(
            'has_party', 'has_obligation', 'benefits_from', 'references', 'limited_by',
            'defined_as', 'triggered_by', 'governed_by', 'amends', 'expires_on',
            name='kgrelationshiptype', create_type=False
        ), nullable=False),

        # Flexible attributes
        sa.Column('properties', postgresql.JSONB(), nullable=False, server_default='{}'),

        # Source tracking
        sa.Column('source_text', sa.Text(), nullable=True),

        # Confidence and metadata
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Indexes for efficient graph traversal
    op.create_index('ix_kg_relationships_contract', 'kg_relationships', ['contract_id'])
    op.create_index('ix_kg_relationships_tenant', 'kg_relationships', ['tenant_id'])
    op.create_index('ix_kg_relationships_source', 'kg_relationships', ['source_entity_id'])
    op.create_index('ix_kg_relationships_target', 'kg_relationships', ['target_entity_id'])
    op.create_index('ix_kg_relationships_type', 'kg_relationships', ['relationship_type'])
    # Composite index for common traversal pattern
    op.create_index('ix_kg_relationships_source_type', 'kg_relationships', ['source_entity_id', 'relationship_type'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_kg_relationships_source_type', table_name='kg_relationships')
    op.drop_index('ix_kg_relationships_type', table_name='kg_relationships')
    op.drop_index('ix_kg_relationships_target', table_name='kg_relationships')
    op.drop_index('ix_kg_relationships_source', table_name='kg_relationships')
    op.drop_index('ix_kg_relationships_tenant', table_name='kg_relationships')
    op.drop_index('ix_kg_relationships_contract', table_name='kg_relationships')

    op.drop_index('ix_kg_entities_contract_type', table_name='kg_entities')
    op.drop_index('ix_kg_entities_normalized_name', table_name='kg_entities')
    op.drop_index('ix_kg_entities_type', table_name='kg_entities')
    op.drop_index('ix_kg_entities_tenant', table_name='kg_entities')
    op.drop_index('ix_kg_entities_contract', table_name='kg_entities')

    # Drop tables
    op.drop_table('kg_relationships')
    op.drop_table('kg_entities')

    # Drop enum types
    op.execute('DROP TYPE kgrelationshiptype')
    op.execute('DROP TYPE kgentitytype')
