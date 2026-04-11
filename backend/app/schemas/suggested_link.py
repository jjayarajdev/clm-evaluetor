"""Pydantic schemas for suggested contract links."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.contract_link import LinkType
from app.models.suggested_link import SuggestionStatus


class ContractBrief(BaseModel):
    """Brief contract info for display in suggestions."""

    id: str
    filename: str
    contract_type: str | None
    counterparty: str | None
    effective_date: str | None
    expiration_date: str | None
    risk_level: str | None

    model_config = {"from_attributes": True}


class SuggestedLinkResponse(BaseModel):
    """Full suggested link response for API."""

    id: str
    source_contract_id: str
    target_contract_id: str
    suggested_link_type: str
    suggested_direction: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str | None
    matching_signals: dict[str, Any] | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_link_id: str | None
    batch_id: str | None
    created_at: datetime
    updated_at: datetime

    # Nested contract info for display
    target_contract: ContractBrief | None = None
    source_contract: ContractBrief | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def _contract_brief(cls, contract) -> ContractBrief | None:
        if not contract:
            return None
        return ContractBrief(
            id=str(contract.id),
            filename=contract.filename,
            contract_type=(
                contract.contract_type.value
                if contract.contract_type else None
            ),
            counterparty=contract.counterparty,
            effective_date=(
                contract.effective_date.isoformat()
                if contract.effective_date else None
            ),
            expiration_date=(
                contract.expiration_date.isoformat()
                if contract.expiration_date else None
            ),
            risk_level=(
                contract.risk_level.value
                if contract.risk_level else None
            ),
        )

    @classmethod
    def from_model(cls, model: "SuggestedContractLink") -> "SuggestedLinkResponse":
        """Create response from model with nested contract."""
        return cls(
            id=str(model.id),
            source_contract_id=str(model.source_contract_id),
            target_contract_id=str(model.target_contract_id),
            suggested_link_type=model.suggested_link_type,
            suggested_direction=model.suggested_direction,
            confidence_score=model.confidence_score,
            reasoning=model.reasoning,
            matching_signals=model.matching_signals,
            status=model.status,
            reviewed_by=str(model.reviewed_by) if model.reviewed_by else None,
            reviewed_at=model.reviewed_at,
            created_link_id=str(model.created_link_id) if model.created_link_id else None,
            batch_id=model.batch_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
            target_contract=cls._contract_brief(model.target_contract),
            source_contract=cls._contract_brief(model.source_contract),
        )


class SuggestedLinksListResponse(BaseModel):
    """Response for list of suggested links."""

    suggestions: list[SuggestedLinkResponse]
    total: int
    pending_count: int


class SuggestedLinkReviewRequest(BaseModel):
    """Request to review (approve/reject/modify) a suggested link."""

    action: Literal["approve", "reject", "modify"]
    modified_link_type: str | None = None  # Only for "modify" action
    notes: str | None = None


class SuggestedLinkReviewResponse(BaseModel):
    """Response after reviewing a suggested link."""

    suggestion_id: str
    action: str
    status: str
    created_link_id: str | None = None
    message: str


class BatchReviewRequest(BaseModel):
    """Request to batch approve/reject multiple suggestions."""

    suggestion_ids: list[str]
    action: Literal["approve", "reject"]
    notes: str | None = None


class BatchReviewResponse(BaseModel):
    """Response for batch review."""

    processed: int
    succeeded: int
    failed: int
    results: list[SuggestedLinkReviewResponse]


class PendingSuggestionsResponse(BaseModel):
    """Response for all pending suggestions for a tenant."""

    total_pending: int
    by_contract: dict[str, int]  # contract_id -> count of pending suggestions
    suggestions: list[SuggestedLinkResponse]
