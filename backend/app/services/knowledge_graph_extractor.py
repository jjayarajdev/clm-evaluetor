"""Knowledge graph extraction service using LLM.

Extracts entities and relationships from contract text to build a knowledge graph.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_graph import (
    KGEntity,
    KGEntityType,
    KGRelationship,
    KGRelationshipType,
)
from app.schemas.knowledge_graph import (
    ExtractedEntity,
    ExtractedRelationship,
    LLMExtractionResult,
)

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


# Extraction prompt for LLM
ORPHAN_RESOLUTION_PROMPT = """You are a contract analysis expert. You are given two lists from the same contract:

1. ORPHAN ENTITIES — extracted entities that have NO relationships to any other entity.
2. CONNECTED ENTITIES — entities that already have relationships.

For each orphan entity, decide ONE action:

- LINK: This orphan should be connected to an existing entity. Provide the relationship.
- MERGE: This orphan is a duplicate of an existing entity (different name, same concept). Provide the target entity name.
- SKIP: No reliable relationship exists. Do not guess — skipping is always acceptable.

Rules:
- Only create a relationship if the source text clearly supports it.
- Never invent relationships that aren't evident from the text.
- When in doubt, SKIP. A missing link is better than a wrong one in a legal contract.
- Use only these relationship types: has_party, has_obligation, benefits_from, references, limited_by, defined_as, triggered_by, governed_by, amends, expires_on

ORPHAN ENTITIES:
{orphans}

CONNECTED ENTITIES:
{connected}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "resolutions": [
    {{"orphan_name": "Claims Deadline", "action": "LINK", "target_entity_name": "Payment Obligation", "relationship_type": "limited_by", "direction": "target_to_orphan", "justification": "The claims deadline limits the payment obligation per Section 4.2"}},
    {{"orphan_name": "Initial Term", "action": "MERGE", "merge_into": "Term of Agreement", "justification": "Both refer to the same contract duration defined in Section 1"}},
    {{"orphan_name": "SOC Setup Due Date", "action": "SKIP", "justification": "No clear relationship to existing entities from source text"}}
  ]
}}

Direction field for LINK actions:
- "orphan_to_target": orphan --[relationship]--> target (e.g., orphan "expires_on" target date)
- "target_to_orphan": target --[relationship]--> orphan (e.g., party "has_obligation" orphan obligation)"""


EXTRACTION_PROMPT = """Extract entities and relationships from this contract section.

ENTITIES to extract:
- party: Companies, people (include role: provider/client/vendor in properties)
- term: Defined terms ("Provider" means..., "Effective Date" means...) - put definition in properties
- obligation: What parties must do (include type: payment/delivery/reporting in properties)
- amount: Money values with context (value, currency in properties)
- date: Key dates (effective, expiration, deadlines) - put date_type and value in properties
- clause: Section references (Section 5.1, Article III) - put section_number and title in properties
- jurisdiction: Governing law - put state/country in properties
- sla_metric: Service level metrics - put metric name and target in properties

RELATIONSHIPS to extract:
- has_party: Contract or clause has a party involved
- has_obligation: Party has an obligation to fulfill
- benefits_from: Party benefits from an obligation
- references: Clause references another clause
- limited_by: Obligation limited by an amount or clause (caps, limits)
- defined_as: Term is defined as another entity
- triggered_by: Obligation triggered by event/condition
- governed_by: Contract governed by jurisdiction
- amends: Clause or contract amends another
- expires_on: Contract or obligation expires on date

CONTRACT TEXT:
{text}

Return ONLY valid JSON with this structure (no markdown, no explanation):
{{
  "entities": [
    {{"entity_type": "party", "name": "Acme Corp", "properties": {{"role": "provider"}}, "source_text": "Acme Corp (\"Provider\")"}},
    {{"entity_type": "term", "name": "Provider", "properties": {{"definition": "Acme Corp"}}, "source_text": "\\"Provider\\" means Acme Corp"}},
    {{"entity_type": "amount", "name": "Liability Cap", "properties": {{"value": 1000000, "currency": "USD"}}, "source_text": "not to exceed $1,000,000"}}
  ],
  "relationships": [
    {{"source_entity_name": "Acme Corp", "target_entity_name": "Payment Obligation", "relationship_type": "has_obligation"}},
    {{"source_entity_name": "Provider", "target_entity_name": "Acme Corp", "relationship_type": "defined_as"}}
  ]
}}"""


async def extract_from_chunk(
    text: str,
    max_chars: int = 6000,
) -> LLMExtractionResult:
    """Extract entities and relationships from a text chunk using LLM.

    Args:
        text: Contract text chunk to process.
        max_chars: Maximum characters to send to LLM.

    Returns:
        LLMExtractionResult with entities and relationships.
    """
    client = get_openai_client()

    # Truncate if needed
    sample = text[:max_chars] if len(text) > max_chars else text

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and efficient for extraction
            messages=[
                {
                    "role": "system",
                    "content": "You are a contract analysis expert. Extract entities and relationships from contract text. Return only valid JSON.",
                },
                {"role": "user", "content": EXTRACTION_PROMPT.format(text=sample)},
            ],
            temperature=0,
            max_tokens=2000,
        )

        result_text = response.choices[0].message.content or "{}"

        # Handle markdown code blocks if present
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        data = json.loads(result_text.strip())

        entities = [
            ExtractedEntity(
                entity_type=e.get("entity_type", "term"),
                name=e.get("name", "Unknown"),
                normalized_name=e.get("name", "").lower().strip(),
                properties=e.get("properties", {}),
                source_text=e.get("source_text"),
            )
            for e in data.get("entities", [])
        ]

        relationships = [
            ExtractedRelationship(
                source_entity_name=r.get("source_entity_name", ""),
                target_entity_name=r.get("target_entity_name", ""),
                relationship_type=r.get("relationship_type", "references"),
                properties=r.get("properties", {}),
                source_text=r.get("source_text"),
            )
            for r in data.get("relationships", [])
        ]

        return LLMExtractionResult(entities=entities, relationships=relationships)

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error in KG extraction: {e}")
        return LLMExtractionResult(entities=[], relationships=[])
    except Exception as e:
        logger.warning(f"KG extraction failed: {e}")
        return LLMExtractionResult(entities=[], relationships=[])


def _split_text_for_extraction(
    text: str,
    chunk_size: int = 5000,
    overlap: int = 500,
) -> list[str]:
    """Split large text into overlapping chunks for processing.

    Args:
        text: Full contract text.
        chunk_size: Maximum size per chunk.
        overlap: Overlap between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at paragraph boundary
        if end < len(text):
            break_point = text.rfind("\n\n", start + chunk_size - 500, end)
            if break_point > start:
                end = break_point
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end
    return chunks


def _deduplicate_entities(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    """Deduplicate entities by normalized name, keeping higher-confidence versions.

    Args:
        entities: List of extracted entities.

    Returns:
        Deduplicated list.
    """
    by_key: dict[tuple[str, str], ExtractedEntity] = {}

    for entity in entities:
        key = (entity.entity_type, entity.normalized_name or entity.name.lower())
        if key not in by_key:
            by_key[key] = entity
        else:
            # Merge properties, preferring non-empty values
            existing = by_key[key]
            merged_props = {**existing.properties, **entity.properties}
            if entity.source_text and not existing.source_text:
                existing.source_text = entity.source_text
            existing.properties = merged_props

    return list(by_key.values())


async def resolve_orphans(
    orphan_entities: list[dict],
    connected_entities: list[dict],
    max_orphans_per_call: int = 40,
) -> list[dict]:
    """Ask LLM to resolve orphan entities by linking, merging, or skipping.

    Args:
        orphan_entities: List of dicts with name, entity_type, source_text.
        connected_entities: List of dicts with name, entity_type.
        max_orphans_per_call: Max orphans per LLM call to stay within token limits.

    Returns:
        List of resolution dicts from LLM.
    """
    client = get_openai_client()
    all_resolutions = []

    # Process in batches if many orphans
    for i in range(0, len(orphan_entities), max_orphans_per_call):
        batch = orphan_entities[i : i + max_orphans_per_call]

        orphan_text = "\n".join(
            f'- [{e["entity_type"]}] "{e["name"]}"'
            + (f' (source: "{e["source_text"][:120]}")' if e.get("source_text") else "")
            for e in batch
        )
        connected_text = "\n".join(
            f'- [{e["entity_type"]}] "{e["name"]}"' for e in connected_entities
        )

        prompt = ORPHAN_RESOLUTION_PROMPT.format(
            orphans=orphan_text, connected=connected_text
        )

        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a contract analysis expert. Resolve orphan entities conservatively. When in doubt, SKIP.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=3000,
            )

            result_text = response.choices[0].message.content or "{}"
            if "```" in result_text:
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]

            data = json.loads(result_text.strip())
            all_resolutions.extend(data.get("resolutions", []))

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Orphan resolution LLM call failed: {e}")

    return all_resolutions


class KnowledgeGraphExtractor:
    """Service for extracting knowledge graph from contract text."""

    def __init__(self, db: AsyncSession):
        """Initialize extractor with database session.

        Args:
            db: Async database session.
        """
        self.db = db

    async def extract_and_store(
        self,
        contract_id: str,
        tenant_id: str,
        contract_text: str,
        force_reextract: bool = False,
    ) -> tuple[int, int]:
        """Extract entities and relationships from contract and store in database.

        Args:
            contract_id: UUID of the contract.
            tenant_id: UUID of the tenant.
            contract_text: Full contract text.
            force_reextract: If True, delete existing data and re-extract.

        Returns:
            Tuple of (entity_count, relationship_count).
        """
        contract_uuid = uuid.UUID(contract_id)
        tenant_uuid = uuid.UUID(tenant_id)

        # Clean up existing if force re-extract
        if force_reextract:
            await self._cleanup_existing(contract_uuid)

        # Split text into chunks
        chunks = _split_text_for_extraction(contract_text)
        logger.info(f"Extracting KG from {len(chunks)} chunks for contract {contract_id}")

        # Extract from all chunks in parallel (with rate limiting)
        all_entities: list[ExtractedEntity] = []
        all_relationships: list[ExtractedRelationship] = []

        batch_size = 5
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            results = await asyncio.gather(
                *[extract_from_chunk(chunk) for chunk in batch],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, LLMExtractionResult):
                    all_entities.extend(result.entities)
                    all_relationships.extend(result.relationships)

        # Deduplicate entities
        unique_entities = _deduplicate_entities(all_entities)
        logger.info(f"Extracted {len(unique_entities)} unique entities from {len(all_entities)} total")

        # Store entities and build name -> id mapping
        entity_map = await self._store_entities(
            contract_uuid, tenant_uuid, unique_entities
        )

        # Store relationships using entity map
        rel_count = await self._store_relationships(
            contract_uuid, tenant_uuid, all_relationships, entity_map
        )

        await self.db.flush()
        logger.info(f"Pass 1: stored {len(entity_map)} entities and {rel_count} relationships")

        # Pass 2: Resolve orphan entities
        pass2_count = await self._resolve_orphan_entities(
            contract_uuid, tenant_uuid, entity_map
        )
        if pass2_count > 0:
            await self.db.flush()
            logger.info(f"Pass 2: resolved {pass2_count} orphan relationships")

        return len(entity_map), rel_count + pass2_count

    async def _cleanup_existing(self, contract_id: uuid.UUID) -> None:
        """Delete existing entities and relationships for a contract.

        Args:
            contract_id: UUID of the contract.
        """
        # Relationships will cascade delete due to foreign key
        await self.db.execute(
            delete(KGEntity).where(KGEntity.contract_id == contract_id)
        )

    async def _store_entities(
        self,
        contract_id: uuid.UUID,
        tenant_id: uuid.UUID,
        entities: list[ExtractedEntity],
    ) -> dict[str, uuid.UUID]:
        """Store entities in database and return name -> id mapping.

        Args:
            contract_id: Contract UUID.
            tenant_id: Tenant UUID.
            entities: List of extracted entities.

        Returns:
            Dict mapping entity names to their UUIDs.
        """
        entity_map: dict[str, uuid.UUID] = {}

        for entity in entities:
            try:
                # Normalize to lowercase for enum matching
                entity_type_str = entity.entity_type.lower()
                entity_type = KGEntityType(entity_type_str)
            except ValueError:
                entity_type = KGEntityType.TERM  # Default fallback

            db_entity = KGEntity(
                contract_id=contract_id,
                tenant_id=tenant_id,
                entity_type=entity_type,
                name=entity.name,
                normalized_name=entity.normalized_name or entity.name.lower(),
                properties=entity.properties,
                source_text=entity.source_text,
                confidence=1.0,
            )
            self.db.add(db_entity)
            await self.db.flush()  # Get the ID

            # Map both original and normalized names
            entity_map[entity.name.lower()] = db_entity.id
            if entity.normalized_name:
                entity_map[entity.normalized_name] = db_entity.id

        return entity_map

    async def _store_relationships(
        self,
        contract_id: uuid.UUID,
        tenant_id: uuid.UUID,
        relationships: list[ExtractedRelationship],
        entity_map: dict[str, uuid.UUID],
    ) -> int:
        """Store relationships in database.

        Args:
            contract_id: Contract UUID.
            tenant_id: Tenant UUID.
            relationships: List of extracted relationships.
            entity_map: Mapping of entity names to UUIDs.

        Returns:
            Number of relationships stored.
        """
        count = 0

        for rel in relationships:
            source_name = rel.source_entity_name.lower()
            target_name = rel.target_entity_name.lower()

            # Skip if entities not found
            if source_name not in entity_map or target_name not in entity_map:
                continue

            try:
                # Normalize to lowercase for enum matching
                rel_type_str = rel.relationship_type.lower()
                rel_type = KGRelationshipType(rel_type_str)
            except ValueError:
                rel_type = KGRelationshipType.REFERENCES  # Default fallback

            db_rel = KGRelationship(
                contract_id=contract_id,
                tenant_id=tenant_id,
                source_entity_id=entity_map[source_name],
                target_entity_id=entity_map[target_name],
                relationship_type=rel_type,
                properties=rel.properties,
                source_text=rel.source_text,
                confidence=1.0,
            )
            self.db.add(db_rel)
            count += 1

        return count

    async def _resolve_orphan_entities(
        self,
        contract_id: uuid.UUID,
        tenant_id: uuid.UUID,
        entity_map: dict[str, uuid.UUID],
    ) -> int:
        """Pass 2: Find orphan entities and ask LLM to resolve them.

        Args:
            contract_id: Contract UUID.
            tenant_id: Tenant UUID.
            entity_map: Name-to-UUID mapping from Pass 1.

        Returns:
            Number of new relationships created.
        """
        # Find entities that have no relationships (orphans)
        all_entities = await self.db.execute(
            select(KGEntity).where(KGEntity.contract_id == contract_id)
        )
        entities = all_entities.scalars().all()

        # Get all relationship source/target IDs for this contract
        all_rels = await self.db.execute(
            select(KGRelationship.source_entity_id, KGRelationship.target_entity_id)
            .where(KGRelationship.contract_id == contract_id)
        )
        connected_ids = set()
        for row in all_rels.all():
            connected_ids.add(row[0])
            connected_ids.add(row[1])

        orphans = [e for e in entities if e.id not in connected_ids]
        connected = [e for e in entities if e.id in connected_ids]

        if not orphans:
            logger.info("No orphan entities found — skipping Pass 2")
            return 0

        logger.info(f"Pass 2: resolving {len(orphans)} orphan entities out of {len(entities)} total")

        # Build dicts for the LLM prompt
        orphan_dicts = [
            {
                "name": e.name,
                "entity_type": e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type),
                "source_text": e.source_text,
            }
            for e in orphans
        ]
        connected_dicts = [
            {
                "name": e.name,
                "entity_type": e.entity_type.value if hasattr(e.entity_type, "value") else str(e.entity_type),
            }
            for e in connected
        ]

        # Build quick lookup: name (lowered) -> entity
        entity_by_name: dict[str, KGEntity] = {}
        for e in entities:
            entity_by_name[e.name.lower()] = e
            if e.normalized_name:
                entity_by_name[e.normalized_name] = e

        # Ask LLM
        resolutions = await resolve_orphans(orphan_dicts, connected_dicts)

        new_rel_count = 0
        merged_count = 0
        skipped_count = 0

        for res in resolutions:
            action = res.get("action", "SKIP").upper()
            orphan_name = res.get("orphan_name", "").lower()
            orphan_entity = entity_by_name.get(orphan_name)

            if not orphan_entity:
                continue

            if action == "LINK":
                target_name = res.get("target_entity_name", "").lower()
                target_entity = entity_by_name.get(target_name)
                if not target_entity:
                    continue

                rel_type_str = res.get("relationship_type", "references").lower()
                try:
                    rel_type = KGRelationshipType(rel_type_str)
                except ValueError:
                    rel_type = KGRelationshipType.REFERENCES

                direction = res.get("direction", "orphan_to_target")
                if direction == "target_to_orphan":
                    source_id = target_entity.id
                    target_id = orphan_entity.id
                else:
                    source_id = orphan_entity.id
                    target_id = target_entity.id

                db_rel = KGRelationship(
                    contract_id=contract_id,
                    tenant_id=tenant_id,
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relationship_type=rel_type,
                    properties={
                        "source": "pass2_resolution",
                        "justification": res.get("justification", ""),
                    },
                    source_text=res.get("justification"),
                    confidence=0.7,
                )
                self.db.add(db_rel)
                new_rel_count += 1

            elif action == "MERGE":
                merge_into_name = res.get("merge_into", "").lower()
                merge_target = entity_by_name.get(merge_into_name)
                if not merge_target:
                    continue

                # Re-point any relationships from orphan to merge target
                # (orphans shouldn't have relationships, but be safe)
                # Then delete the orphan entity
                await self.db.execute(
                    delete(KGEntity).where(KGEntity.id == orphan_entity.id)
                )
                merged_count += 1

            else:
                skipped_count += 1

        logger.info(
            f"Pass 2 results: {new_rel_count} linked, {merged_count} merged, {skipped_count} skipped"
        )
        return new_rel_count

    async def get_extraction_stats(
        self,
        contract_id: str,
    ) -> dict[str, Any]:
        """Get statistics about extracted knowledge graph.

        Args:
            contract_id: UUID of the contract.

        Returns:
            Dict with entity and relationship counts by type.
        """
        contract_uuid = uuid.UUID(contract_id)

        # Count entities by type
        entities_result = await self.db.execute(
            select(KGEntity.entity_type, KGEntity.id)
            .where(KGEntity.contract_id == contract_uuid)
        )
        entities = entities_result.all()

        entity_counts: dict[str, int] = {}
        for entity_type, _ in entities:
            type_str = entity_type.value if hasattr(entity_type, "value") else str(entity_type)
            entity_counts[type_str] = entity_counts.get(type_str, 0) + 1

        # Count relationships by type
        rels_result = await self.db.execute(
            select(KGRelationship.relationship_type, KGRelationship.id)
            .where(KGRelationship.contract_id == contract_uuid)
        )
        rels = rels_result.all()

        rel_counts: dict[str, int] = {}
        for rel_type, _ in rels:
            type_str = rel_type.value if hasattr(rel_type, "value") else str(rel_type)
            rel_counts[type_str] = rel_counts.get(type_str, 0) + 1

        return {
            "total_entities": len(entities),
            "total_relationships": len(rels),
            "entities_by_type": entity_counts,
            "relationships_by_type": rel_counts,
        }


# Singleton instance
_extractor: KnowledgeGraphExtractor | None = None


async def get_knowledge_graph_extractor(db: AsyncSession) -> KnowledgeGraphExtractor:
    """Get KnowledgeGraphExtractor instance.

    Args:
        db: Database session.

    Returns:
        KnowledgeGraphExtractor instance.
    """
    return KnowledgeGraphExtractor(db)
