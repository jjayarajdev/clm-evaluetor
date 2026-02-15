"""Pydantic schemas for Master Data (SLA and Milestone configurations)."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ============================================================================
# SLA Master Data Schemas
# ============================================================================


class SLAMasterDataCreate(BaseModel):
    """Request to create an SLA master data entry."""

    reference_code: str = Field(..., max_length=50, description="SLA reference code, e.g., '12.1', '2.1.1'")
    name: str = Field(..., max_length=200, description="SLA name")
    description: str | None = Field(None, max_length=2000, description="Detailed description")
    target_value: Decimal = Field(..., description="Target performance value (e.g., 0.99 for 99%)")
    minimum_value: Decimal | None = Field(None, description="Minimum acceptable value (breach threshold)")
    typical_performance: Decimal | None = Field(None, description="Expected typical performance")
    volatility: Decimal | None = Field(None, description="Expected variance")
    category: str | None = Field(None, max_length=100, description="SLA category")
    service_tower: str | None = Field(None, max_length=100, description="Service tower")
    is_active: bool = Field(True, description="Whether this SLA config is active")


class SLAMasterDataUpdate(BaseModel):
    """Request to update an SLA master data entry."""

    reference_code: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    target_value: Decimal | None = None
    minimum_value: Decimal | None = None
    typical_performance: Decimal | None = None
    volatility: Decimal | None = None
    category: str | None = Field(None, max_length=100)
    service_tower: str | None = Field(None, max_length=100)
    is_active: bool | None = None


class SLAMasterDataResponse(BaseModel):
    """Response model for SLA master data."""

    id: str
    reference_code: str
    name: str
    description: str | None
    target_value: float
    minimum_value: float | None
    typical_performance: float | None
    volatility: float | None
    category: str | None
    service_tower: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SLAMasterDataListResponse(BaseModel):
    """Response model for list of SLA master data."""

    items: list[SLAMasterDataResponse]
    total: int


# ============================================================================
# Milestone Master Data Schemas
# ============================================================================


class MilestoneMasterDataCreate(BaseModel):
    """Request to create a milestone master data entry."""

    milestone_code: str = Field(..., max_length=50, description="Milestone code, e.g., 'MS-2.1'")
    name: str = Field(..., max_length=200, description="Milestone name")
    description: str | None = Field(None, max_length=2000, description="Detailed description")
    baseline_days_from_start: int = Field(..., ge=0, description="Days from project start")
    dependencies: list[str] = Field(default_factory=list, description="List of dependent milestone codes")
    credit_at_risk: Decimal | None = Field(None, description="Service credit at risk")
    is_active: bool = Field(True, description="Whether this milestone config is active")


class MilestoneMasterDataUpdate(BaseModel):
    """Request to update a milestone master data entry."""

    milestone_code: str | None = Field(None, max_length=50)
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    baseline_days_from_start: int | None = Field(None, ge=0)
    dependencies: list[str] | None = None
    credit_at_risk: Decimal | None = None
    is_active: bool | None = None


class MilestoneMasterDataResponse(BaseModel):
    """Response model for milestone master data."""

    id: str
    milestone_code: str
    name: str
    description: str | None
    baseline_days_from_start: int
    dependencies: list[str]
    credit_at_risk: float | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MilestoneMasterDataListResponse(BaseModel):
    """Response model for list of milestone master data."""

    items: list[MilestoneMasterDataResponse]
    total: int


# ============================================================================
# Seed Data Schemas
# ============================================================================


class SeedResultResponse(BaseModel):
    """Response model for seed operation."""

    seeded: int
    skipped: int
    message: str
