"""Data models for hierarchy detection pipeline."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field


class RelationshipType(str, enum.Enum):
    SAME_DOCUMENT = "same_document"
    SAME_DOCUMENT_FAMILY = "same_document_family"
    SAME_MASTER_FRAMEWORK = "same_master_framework"
    RELATED_BUT_INDIRECT = "related_but_indirect"
    UNRELATED = "unrelated"


@dataclass
class PartyInfo:
    name: str
    role: str | None = None  # "client", "provider", "guarantor", etc.


@dataclass
class ParentReference:
    referenced_type: str | None = None  # "MSA", "Exhibit 4", etc.
    referenced_title: str | None = None
    relationship: str | None = None  # "child_of", "amendment_to", etc.
    party_names: list[str] = field(default_factory=list)
    referenced_date: str | None = None
    reference_text: str | None = None


@dataclass
class DocumentCard:
    """Rich metadata extracted from a single contract document."""

    contract_id: uuid.UUID
    filename: str

    # Identity
    title: str | None = None
    doc_type: str | None = None  # MSA, SOW, EXHIBIT, ATTACHMENT, LSA, NDA, AMENDMENT, etc.
    doc_identifier: str | None = None  # "Exhibit 3", "Attachment 4-A", "Amendment No. 2"
    doc_number: str | None = None  # Normalised: "3", "4-A", "2"

    # Parties
    parties: list[PartyInfo] = field(default_factory=list)

    # Relationships detected in text
    parent_references: list[ParentReference] = field(default_factory=list)
    child_references: list[str] = field(default_factory=list)  # "Exhibit 1", "Attachment 4-A", etc.

    # Content
    subject_summary: str | None = None
    effective_date: str | None = None
    term: str | None = None
    governing_law: str | None = None
    financial_summary: str | None = None

    # Metadata
    extraction_confidence: float = 0.0
    content_hash: str | None = None


@dataclass
class PairCandidate:
    """A candidate pair of documents to classify."""

    contract_a_id: uuid.UUID
    contract_b_id: uuid.UUID
    generation_reasons: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class ClassifiedPair:
    """Result of pairwise relationship classification."""

    contract_a_id: uuid.UUID
    contract_b_id: uuid.UUID
    relationship: RelationshipType
    parent_id: uuid.UUID | None = None
    child_id: uuid.UUID | None = None
    link_type: str | None = None  # Maps to LinkType enum values
    confidence: float = 0.0
    reasoning: str = ""
