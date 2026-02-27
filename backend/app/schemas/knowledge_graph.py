"""Pydantic schemas for knowledge graph API."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# Entity type literals matching KGEntityType enum
EntityType = Literal[
    "party", "clause", "obligation", "term", "date", "amount", "jurisdiction", "sla_metric"
]

# Relationship type literals matching KGRelationshipType enum
RelationshipType = Literal[
    "has_party", "has_obligation", "benefits_from", "references", "limited_by",
    "defined_as", "triggered_by", "governed_by", "amends", "expires_on"
]


# Request schemas
class KGEntityCreate(BaseModel):
    """Request to create a knowledge graph entity."""

    entity_type: EntityType
    name: str = Field(..., max_length=500)
    normalized_name: str | None = Field(None, max_length=500)
    properties: dict = Field(default_factory=dict)
    source_text: str | None = None
    source_section: str | None = Field(None, max_length=50)
    source_page: int | None = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class KGRelationshipCreate(BaseModel):
    """Request to create a knowledge graph relationship."""

    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    properties: dict = Field(default_factory=dict)
    source_text: str | None = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class KGBulkExtractRequest(BaseModel):
    """Request to extract knowledge graph from contract text."""

    contract_id: str
    force_reextract: bool = Field(False, description="Delete existing entities and re-extract")


# Response schemas
class KGEntityResponse(BaseModel):
    """Response model for a knowledge graph entity."""

    id: str
    contract_id: str
    tenant_id: str
    entity_type: EntityType
    name: str
    normalized_name: str | None
    properties: dict
    source_text: str | None
    source_section: str | None
    source_page: int | None
    confidence: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KGRelationshipResponse(BaseModel):
    """Response model for a knowledge graph relationship."""

    id: str
    contract_id: str
    tenant_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    properties: dict
    source_text: str | None
    confidence: float
    created_at: datetime

    class Config:
        from_attributes = True


class KGEntityWithRelationships(KGEntityResponse):
    """Entity with its outgoing and incoming relationships."""

    outgoing_relationships: list["KGRelationshipResponse"] = []
    incoming_relationships: list["KGRelationshipResponse"] = []


class KGGraphResponse(BaseModel):
    """Complete knowledge graph for a contract."""

    contract_id: str
    entities: list[KGEntityResponse]
    relationships: list[KGRelationshipResponse]
    stats: "KGGraphStats"


class KGGraphStats(BaseModel):
    """Statistics about the knowledge graph."""

    total_entities: int
    total_relationships: int
    entities_by_type: dict[str, int]
    relationships_by_type: dict[str, int]


class KGTermResolution(BaseModel):
    """Result of resolving a defined term."""

    term: str
    definition: str | None
    resolved_entity: KGEntityResponse | None
    confidence: float


class KGPartyObligations(BaseModel):
    """Obligations for a specific party."""

    party_name: str
    party_id: str
    obligations: list["KGObligationDetail"]


class KGObligationDetail(BaseModel):
    """Detailed obligation with limits and beneficiaries."""

    obligation_id: str
    obligation_name: str
    description: str | None
    limited_by: list[KGEntityResponse] = []
    beneficiaries: list[KGEntityResponse] = []
    triggered_by: list[KGEntityResponse] = []


class KGRelatedClauses(BaseModel):
    """Clauses related to a given clause."""

    source_clause: KGEntityResponse
    related_clauses: list["KGClauseRelation"]


class KGClauseRelation(BaseModel):
    """A related clause with relationship info."""

    clause: KGEntityResponse
    relationship_type: RelationshipType
    depth: int = Field(..., description="How many hops away from source")


class KGRiskPattern(BaseModel):
    """Detected risk pattern in the knowledge graph."""

    risk_type: str
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    related_entities: list[KGEntityResponse]
    recommendation: str | None


class KGRiskAnalysis(BaseModel):
    """Risk analysis based on knowledge graph patterns."""

    contract_id: str
    risk_patterns: list[KGRiskPattern]
    summary: str


# LLM extraction schemas (for internal use)
class ExtractedEntity(BaseModel):
    """Entity extracted by LLM."""

    entity_type: EntityType
    name: str
    normalized_name: str | None = None
    properties: dict = Field(default_factory=dict)
    source_text: str | None = None


class ExtractedRelationship(BaseModel):
    """Relationship extracted by LLM."""

    source_entity_name: str  # Reference by name for linking
    target_entity_name: str
    relationship_type: RelationshipType
    properties: dict = Field(default_factory=dict)
    source_text: str | None = None


class LLMExtractionResult(BaseModel):
    """Result from LLM entity/relationship extraction."""

    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]


# Update forward references
KGEntityWithRelationships.model_rebuild()
KGGraphResponse.model_rebuild()
KGPartyObligations.model_rebuild()
KGRelatedClauses.model_rebuild()
