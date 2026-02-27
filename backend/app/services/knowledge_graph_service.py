"""Knowledge graph query service.

Provides methods for traversing and querying the contract knowledge graph.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.knowledge_graph import (
    KGEntity,
    KGEntityType,
    KGRelationship,
    KGRelationshipType,
)
from app.schemas.knowledge_graph import (
    KGClauseRelation,
    KGEntityResponse,
    KGEntityWithRelationships,
    KGGraphResponse,
    KGGraphStats,
    KGObligationDetail,
    KGPartyObligations,
    KGRelatedClauses,
    KGRelationshipResponse,
    KGRiskAnalysis,
    KGRiskPattern,
    KGTermResolution,
)

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """Service for querying the contract knowledge graph."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def get_full_graph(
        self,
        contract_id: str,
        tenant_id: str,
    ) -> KGGraphResponse:
        """Get the complete knowledge graph for a contract.

        Args:
            contract_id: UUID of the contract.
            tenant_id: UUID of the tenant.

        Returns:
            KGGraphResponse with all entities and relationships.
        """
        contract_uuid = uuid.UUID(contract_id)
        tenant_uuid = uuid.UUID(tenant_id)

        # Get all entities
        entities_result = await self.db.execute(
            select(KGEntity)
            .where(
                and_(
                    KGEntity.contract_id == contract_uuid,
                    KGEntity.tenant_id == tenant_uuid,
                )
            )
            .order_by(KGEntity.entity_type, KGEntity.name)
        )
        entities = entities_result.scalars().all()

        # Get all relationships
        rels_result = await self.db.execute(
            select(KGRelationship)
            .where(
                and_(
                    KGRelationship.contract_id == contract_uuid,
                    KGRelationship.tenant_id == tenant_uuid,
                )
            )
        )
        relationships = rels_result.scalars().all()

        # Build stats
        entity_counts: dict[str, int] = {}
        for e in entities:
            type_str = e.entity_type.value
            entity_counts[type_str] = entity_counts.get(type_str, 0) + 1

        rel_counts: dict[str, int] = {}
        for r in relationships:
            type_str = r.relationship_type.value
            rel_counts[type_str] = rel_counts.get(type_str, 0) + 1

        return KGGraphResponse(
            contract_id=contract_id,
            entities=[self._entity_to_response(e) for e in entities],
            relationships=[self._relationship_to_response(r) for r in relationships],
            stats=KGGraphStats(
                total_entities=len(entities),
                total_relationships=len(relationships),
                entities_by_type=entity_counts,
                relationships_by_type=rel_counts,
            ),
        )

    async def resolve_term(
        self,
        contract_id: str,
        term_name: str,
    ) -> KGTermResolution:
        """Resolve a defined term to its actual entity.

        Example: "Provider" -> "Acme Corp"

        Args:
            contract_id: UUID of the contract.
            term_name: Name of the term to resolve.

        Returns:
            KGTermResolution with definition and resolved entity.
        """
        contract_uuid = uuid.UUID(contract_id)
        normalized_term = term_name.lower().strip()

        # Find the term entity
        term_result = await self.db.execute(
            select(KGEntity)
            .where(
                and_(
                    KGEntity.contract_id == contract_uuid,
                    KGEntity.normalized_name == normalized_term,
                    KGEntity.entity_type == KGEntityType.TERM,
                )
            )
        )
        term_entity = term_result.scalar_one_or_none()

        if not term_entity:
            # Try to find any entity with this name
            any_result = await self.db.execute(
                select(KGEntity)
                .where(
                    and_(
                        KGEntity.contract_id == contract_uuid,
                        KGEntity.normalized_name == normalized_term,
                    )
                )
            )
            any_entity = any_result.scalar_one_or_none()
            if any_entity:
                return KGTermResolution(
                    term=term_name,
                    definition=None,
                    resolved_entity=self._entity_to_response(any_entity),
                    confidence=0.8,
                )
            return KGTermResolution(
                term=term_name,
                definition=None,
                resolved_entity=None,
                confidence=0.0,
            )

        # Find what this term is defined as
        definition_result = await self.db.execute(
            select(KGRelationship, KGEntity)
            .join(KGEntity, KGEntity.id == KGRelationship.target_entity_id)
            .where(
                and_(
                    KGRelationship.source_entity_id == term_entity.id,
                    KGRelationship.relationship_type == KGRelationshipType.DEFINED_AS,
                )
            )
        )
        definition_row = definition_result.first()

        definition = term_entity.properties.get("definition")
        resolved_entity = None

        if definition_row:
            _, target_entity = definition_row
            resolved_entity = self._entity_to_response(target_entity)
            if not definition:
                definition = target_entity.name

        return KGTermResolution(
            term=term_name,
            definition=definition,
            resolved_entity=resolved_entity,
            confidence=term_entity.confidence,
        )

    async def get_party_obligations(
        self,
        contract_id: str,
        party_name: str | None = None,
    ) -> list[KGPartyObligations]:
        """Get obligations for parties with their limits and beneficiaries.

        Args:
            contract_id: UUID of the contract.
            party_name: Optional party name to filter by.

        Returns:
            List of KGPartyObligations with obligation details.
        """
        contract_uuid = uuid.UUID(contract_id)

        # Build party query
        party_query = select(KGEntity).where(
            and_(
                KGEntity.contract_id == contract_uuid,
                KGEntity.entity_type == KGEntityType.PARTY,
            )
        )
        if party_name:
            party_query = party_query.where(
                KGEntity.normalized_name == party_name.lower().strip()
            )

        parties_result = await self.db.execute(party_query)
        parties = parties_result.scalars().all()

        results: list[KGPartyObligations] = []

        for party in parties:
            # Get obligations for this party
            obls_result = await self.db.execute(
                select(KGRelationship, KGEntity)
                .join(KGEntity, KGEntity.id == KGRelationship.target_entity_id)
                .where(
                    and_(
                        KGRelationship.source_entity_id == party.id,
                        KGRelationship.relationship_type == KGRelationshipType.HAS_OBLIGATION,
                    )
                )
            )
            obligations = obls_result.all()

            obl_details: list[KGObligationDetail] = []

            for _, obl_entity in obligations:
                # Get limits for this obligation
                limits_result = await self.db.execute(
                    select(KGEntity)
                    .join(
                        KGRelationship,
                        KGRelationship.target_entity_id == KGEntity.id,
                    )
                    .where(
                        and_(
                            KGRelationship.source_entity_id == obl_entity.id,
                            KGRelationship.relationship_type == KGRelationshipType.LIMITED_BY,
                        )
                    )
                )
                limits = [self._entity_to_response(e) for e in limits_result.scalars().all()]

                # Get beneficiaries
                benef_result = await self.db.execute(
                    select(KGEntity)
                    .join(
                        KGRelationship,
                        KGRelationship.target_entity_id == KGEntity.id,
                    )
                    .where(
                        and_(
                            KGRelationship.source_entity_id == obl_entity.id,
                            KGRelationship.relationship_type == KGRelationshipType.BENEFITS_FROM,
                        )
                    )
                )
                beneficiaries = [self._entity_to_response(e) for e in benef_result.scalars().all()]

                # Get triggers
                triggers_result = await self.db.execute(
                    select(KGEntity)
                    .join(
                        KGRelationship,
                        KGRelationship.target_entity_id == KGEntity.id,
                    )
                    .where(
                        and_(
                            KGRelationship.source_entity_id == obl_entity.id,
                            KGRelationship.relationship_type == KGRelationshipType.TRIGGERED_BY,
                        )
                    )
                )
                triggers = [self._entity_to_response(e) for e in triggers_result.scalars().all()]

                obl_details.append(
                    KGObligationDetail(
                        obligation_id=str(obl_entity.id),
                        obligation_name=obl_entity.name,
                        description=obl_entity.properties.get("description"),
                        limited_by=limits,
                        beneficiaries=beneficiaries,
                        triggered_by=triggers,
                    )
                )

            results.append(
                KGPartyObligations(
                    party_name=party.name,
                    party_id=str(party.id),
                    obligations=obl_details,
                )
            )

        return results

    async def get_related_clauses(
        self,
        contract_id: str,
        clause_name: str,
        max_depth: int = 5,
    ) -> KGRelatedClauses:
        """Find clauses related to a given clause using recursive traversal.

        Args:
            contract_id: UUID of the contract.
            clause_name: Name or section number of the source clause.
            max_depth: Maximum traversal depth.

        Returns:
            KGRelatedClauses with source and related clauses.
        """
        contract_uuid = uuid.UUID(contract_id)
        normalized_name = clause_name.lower().strip()

        # Find the source clause
        source_result = await self.db.execute(
            select(KGEntity)
            .where(
                and_(
                    KGEntity.contract_id == contract_uuid,
                    or_(
                        KGEntity.normalized_name == normalized_name,
                        KGEntity.name.ilike(f"%{clause_name}%"),
                    ),
                    KGEntity.entity_type == KGEntityType.CLAUSE,
                )
            )
        )
        source_entity = source_result.scalar_one_or_none()

        if not source_entity:
            raise ValueError(f"Clause not found: {clause_name}")

        # Use recursive CTE to find related clauses
        # This is a PostgreSQL-specific feature
        cte_query = text("""
            WITH RECURSIVE clause_chain AS (
                -- Base case: the source clause
                SELECT
                    e.id,
                    e.name,
                    r.relationship_type,
                    0 as depth,
                    ARRAY[e.id] as path
                FROM kg_entities e
                LEFT JOIN kg_relationships r ON r.source_entity_id = e.id
                WHERE e.id = :source_id

                UNION ALL

                -- Recursive case: follow relationships
                SELECT
                    e2.id,
                    e2.name,
                    r.relationship_type,
                    cc.depth + 1,
                    cc.path || e2.id
                FROM clause_chain cc
                JOIN kg_relationships r ON (r.source_entity_id = cc.id OR r.target_entity_id = cc.id)
                JOIN kg_entities e2 ON e2.id = CASE
                    WHEN r.source_entity_id = cc.id THEN r.target_entity_id
                    ELSE r.source_entity_id
                END
                WHERE r.relationship_type IN ('references', 'amends')
                  AND e2.id != ALL(cc.path)
                  AND cc.depth < :max_depth
                  AND e2.entity_type = 'clause'
            )
            SELECT DISTINCT id, name, relationship_type, depth
            FROM clause_chain
            WHERE depth > 0
            ORDER BY depth;
        """)

        result = await self.db.execute(
            cte_query,
            {"source_id": source_entity.id, "max_depth": max_depth},
        )
        rows = result.fetchall()

        # Fetch full entities for the related clauses
        related_ids = [row[0] for row in rows]
        depth_map = {row[0]: (row[2], row[3]) for row in rows}  # id -> (rel_type, depth)

        if related_ids:
            entities_result = await self.db.execute(
                select(KGEntity).where(KGEntity.id.in_(related_ids))
            )
            related_entities = entities_result.scalars().all()
        else:
            related_entities = []

        related_clauses = []
        for entity in related_entities:
            rel_type, depth = depth_map.get(entity.id, ("references", 1))
            related_clauses.append(
                KGClauseRelation(
                    clause=self._entity_to_response(entity),
                    relationship_type=rel_type or "references",
                    depth=depth,
                )
            )

        return KGRelatedClauses(
            source_clause=self._entity_to_response(source_entity),
            related_clauses=related_clauses,
        )

    async def detect_risk_patterns(
        self,
        contract_id: str,
        tenant_id: str,
    ) -> KGRiskAnalysis:
        """Detect risk patterns in the knowledge graph.

        Patterns detected:
        - Unlimited obligations (no cap)
        - One-sided obligations (all on one party)
        - Missing jurisdictions
        - Undefined terms

        Args:
            contract_id: UUID of the contract.
            tenant_id: UUID of the tenant.

        Returns:
            KGRiskAnalysis with detected patterns.
        """
        contract_uuid = uuid.UUID(contract_id)
        risks: list[KGRiskPattern] = []

        # Pattern 1: Unlimited obligations (no LIMITED_BY relationship)
        unlimited_query = text("""
            SELECT
                obl.id,
                obl.name,
                obl.properties,
                party.name as party_name
            FROM kg_entities obl
            JOIN kg_relationships r1 ON r1.target_entity_id = obl.id
                AND r1.relationship_type = 'has_obligation'
            JOIN kg_entities party ON party.id = r1.source_entity_id
            LEFT JOIN kg_relationships r2 ON r2.source_entity_id = obl.id
                AND r2.relationship_type = 'limited_by'
            WHERE r2.id IS NULL
              AND obl.contract_id = :contract_id
              AND obl.entity_type = 'obligation'
              AND (
                  obl.properties->>'type' IN ('indemnification', 'liability')
                  OR obl.name ILIKE '%indemnif%'
                  OR obl.name ILIKE '%liabil%'
              );
        """)

        unlimited_result = await self.db.execute(
            unlimited_query, {"contract_id": contract_uuid}
        )
        unlimited_rows = unlimited_result.fetchall()

        for row in unlimited_rows:
            obl_id, obl_name, _, party_name = row
            risks.append(
                KGRiskPattern(
                    risk_type="unlimited_obligation",
                    severity="high",
                    description=f"Obligation '{obl_name}' on {party_name} has no liability cap",
                    related_entities=[],  # Would need to fetch entities
                    recommendation="Add a liability cap clause or negotiate a monetary limit",
                )
            )

        # Pattern 2: No governing jurisdiction
        jurisdiction_result = await self.db.execute(
            select(KGEntity)
            .where(
                and_(
                    KGEntity.contract_id == contract_uuid,
                    KGEntity.entity_type == KGEntityType.JURISDICTION,
                )
            )
        )
        jurisdictions = jurisdiction_result.scalars().all()

        if not jurisdictions:
            risks.append(
                KGRiskPattern(
                    risk_type="missing_jurisdiction",
                    severity="medium",
                    description="No governing law or jurisdiction clause found",
                    related_entities=[],
                    recommendation="Add a governing law clause specifying jurisdiction",
                )
            )

        # Pattern 3: Undefined terms (terms without DEFINED_AS relationship)
        undefined_query = text("""
            SELECT
                term.id,
                term.name
            FROM kg_entities term
            LEFT JOIN kg_relationships r ON r.source_entity_id = term.id
                AND r.relationship_type = 'defined_as'
            WHERE term.contract_id = :contract_id
              AND term.entity_type = 'term'
              AND r.id IS NULL
              AND term.properties->>'definition' IS NULL;
        """)

        undefined_result = await self.db.execute(
            undefined_query, {"contract_id": contract_uuid}
        )
        undefined_rows = undefined_result.fetchall()

        if len(undefined_rows) > 3:  # Only flag if many undefined
            risks.append(
                KGRiskPattern(
                    risk_type="undefined_terms",
                    severity="low",
                    description=f"{len(undefined_rows)} terms are used but not defined",
                    related_entities=[],
                    recommendation="Add definitions for key terms to avoid ambiguity",
                )
            )

        # Generate summary
        risk_count = len(risks)
        high_risks = sum(1 for r in risks if r.severity == "high")
        summary = f"Found {risk_count} potential issues"
        if high_risks > 0:
            summary += f", including {high_risks} high severity"

        return KGRiskAnalysis(
            contract_id=contract_id,
            risk_patterns=risks,
            summary=summary,
        )

    async def get_entity_by_id(
        self,
        entity_id: str,
    ) -> KGEntityWithRelationships | None:
        """Get an entity with its relationships.

        Args:
            entity_id: UUID of the entity.

        Returns:
            KGEntityWithRelationships or None if not found.
        """
        entity_uuid = uuid.UUID(entity_id)

        result = await self.db.execute(
            select(KGEntity)
            .options(
                selectinload(KGEntity.outgoing_relationships),
                selectinload(KGEntity.incoming_relationships),
            )
            .where(KGEntity.id == entity_uuid)
        )
        entity = result.scalar_one_or_none()

        if not entity:
            return None

        return KGEntityWithRelationships(
            **self._entity_to_response(entity).model_dump(),
            outgoing_relationships=[
                self._relationship_to_response(r) for r in entity.outgoing_relationships
            ],
            incoming_relationships=[
                self._relationship_to_response(r) for r in entity.incoming_relationships
            ],
        )

    async def search_entities(
        self,
        contract_id: str,
        entity_type: str | None = None,
        search_term: str | None = None,
        limit: int = 50,
    ) -> list[KGEntityResponse]:
        """Search for entities in a contract.

        Args:
            contract_id: UUID of the contract.
            entity_type: Optional entity type filter.
            search_term: Optional search term for name.
            limit: Maximum results to return.

        Returns:
            List of matching entities.
        """
        contract_uuid = uuid.UUID(contract_id)

        query = select(KGEntity).where(KGEntity.contract_id == contract_uuid)

        if entity_type:
            try:
                type_enum = KGEntityType(entity_type)
                query = query.where(KGEntity.entity_type == type_enum)
            except ValueError:
                pass

        if search_term:
            query = query.where(
                or_(
                    KGEntity.name.ilike(f"%{search_term}%"),
                    KGEntity.normalized_name.ilike(f"%{search_term}%"),
                )
            )

        query = query.order_by(KGEntity.name).limit(limit)

        result = await self.db.execute(query)
        entities = result.scalars().all()

        return [self._entity_to_response(e) for e in entities]

    def _entity_to_response(self, entity: KGEntity) -> KGEntityResponse:
        """Convert KGEntity to response model."""
        return KGEntityResponse(
            id=str(entity.id),
            contract_id=str(entity.contract_id),
            tenant_id=str(entity.tenant_id),
            entity_type=entity.entity_type.value,
            name=entity.name,
            normalized_name=entity.normalized_name,
            properties=entity.properties,
            source_text=entity.source_text,
            source_section=entity.source_section,
            source_page=entity.source_page,
            confidence=entity.confidence,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _relationship_to_response(self, rel: KGRelationship) -> KGRelationshipResponse:
        """Convert KGRelationship to response model."""
        return KGRelationshipResponse(
            id=str(rel.id),
            contract_id=str(rel.contract_id),
            tenant_id=str(rel.tenant_id),
            source_entity_id=str(rel.source_entity_id),
            target_entity_id=str(rel.target_entity_id),
            relationship_type=rel.relationship_type.value,
            properties=rel.properties,
            source_text=rel.source_text,
            confidence=rel.confidence,
            created_at=rel.created_at,
        )


async def get_knowledge_graph_service(db: AsyncSession) -> KnowledgeGraphService:
    """Get KnowledgeGraphService instance.

    Args:
        db: Database session.

    Returns:
        KnowledgeGraphService instance.
    """
    return KnowledgeGraphService(db)
