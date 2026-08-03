"""Data models for hierarchy detection pipeline."""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field


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

    def to_dict(self) -> dict:
        """JSON-serializable form for the contracts.hierarchy_card cache."""
        d = asdict(self)
        d["contract_id"] = str(self.contract_id)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> DocumentCard:
        """Rebuild a card from its cached JSON form (tolerant of missing keys)."""
        return cls(
            contract_id=uuid.UUID(str(data["contract_id"])),
            filename=data.get("filename") or "",
            title=data.get("title"),
            doc_type=data.get("doc_type"),
            doc_identifier=data.get("doc_identifier"),
            doc_number=data.get("doc_number"),
            parties=[
                PartyInfo(name=p["name"], role=p.get("role"))
                for p in data.get("parties") or []
                if isinstance(p, dict) and p.get("name")
            ],
            parent_references=[
                ParentReference(
                    referenced_type=pr.get("referenced_type"),
                    referenced_title=pr.get("referenced_title"),
                    relationship=pr.get("relationship"),
                    party_names=pr.get("party_names") or [],
                    referenced_date=pr.get("referenced_date"),
                    reference_text=pr.get("reference_text"),
                )
                for pr in data.get("parent_references") or []
                if isinstance(pr, dict)
            ],
            child_references=[str(c) for c in data.get("child_references") or [] if c],
            subject_summary=data.get("subject_summary"),
            effective_date=data.get("effective_date"),
            term=data.get("term"),
            governing_law=data.get("governing_law"),
            financial_summary=data.get("financial_summary"),
            extraction_confidence=float(data.get("extraction_confidence") or 0.0),
            content_hash=data.get("content_hash"),
        )


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
