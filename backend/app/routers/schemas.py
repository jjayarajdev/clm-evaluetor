"""Schema management and extraction API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.contract import Contract
from app.schemas import (
    get_schema_registry,
    get_schema_extractor,
    extract_with_schema,
    ExtractionResult,
)

router = APIRouter(prefix="/api/schemas", tags=["Schemas"])


class SchemaListItem(BaseModel):
    """Schema summary for listing."""

    schema_id: str
    contract_type: str
    version: str
    description: str


class SchemaDetailResponse(BaseModel):
    """Full schema details."""

    schema_id: str
    contract_type: str
    version: str
    description: str
    sections: dict[str, Any]
    extraction_model: str
    extraction_temperature: float
    max_tokens: int
    required_sections: list[str]
    json_template: dict[str, Any]


class ExtractRequest(BaseModel):
    """Request to extract data from contract text."""

    contract_text: str
    schema_id: str | None = None
    contract_type: str | None = None


class ExtractFromContractRequest(BaseModel):
    """Request to extract data from an existing contract."""

    schema_id: str | None = None
    contract_type: str | None = None
    save: bool = True  # Save extracted data to contract


@router.get("", response_model=list[SchemaListItem])
async def list_schemas(
    current_user: User = Depends(get_current_user),
) -> list[SchemaListItem]:
    """List all available extraction schemas."""
    registry = get_schema_registry()
    schemas = registry.list_schemas()

    return [SchemaListItem(**s) for s in schemas]


@router.get("/{schema_id}", response_model=SchemaDetailResponse)
async def get_schema(
    schema_id: str,
    current_user: User = Depends(get_current_user),
) -> SchemaDetailResponse:
    """Get details of a specific schema including the JSON template."""
    registry = get_schema_registry()
    schema = registry.get_schema(schema_id)

    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found: {schema_id}")

    # Convert sections to dict format
    sections_dict = {}
    for name, section in schema.sections.items():
        sections_dict[name] = {
            "description": section.description,
            "priority": section.priority,
            "fields": {
                field_name: {
                    "type": field.type.value,
                    "description": field.description,
                    "required": field.required,
                }
                for field_name, field in section.fields.items()
            },
        }

    return SchemaDetailResponse(
        schema_id=schema.schema_id,
        contract_type=schema.contract_type,
        version=schema.version,
        description=schema.description,
        sections=sections_dict,
        extraction_model=schema.extraction_model,
        extraction_temperature=schema.extraction_temperature,
        max_tokens=schema.max_tokens,
        required_sections=schema.required_sections,
        json_template=schema.get_json_template(),
    )


@router.get("/{schema_id}/template")
async def get_schema_template(
    schema_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get just the JSON template for a schema."""
    registry = get_schema_registry()
    schema = registry.get_schema(schema_id)

    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found: {schema_id}")

    return schema.get_json_template()


@router.get("/{schema_id}/prompt")
async def get_schema_prompt(
    schema_id: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Get the generated extraction prompt for a schema."""
    registry = get_schema_registry()
    schema = registry.get_schema(schema_id)

    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema not found: {schema_id}")

    return {
        "schema_id": schema_id,
        "prompt": schema.to_prompt_instructions(),
    }


@router.post("/extract", response_model=ExtractionResult)
async def extract_from_text(
    request: ExtractRequest,
    current_user: User = Depends(get_current_user),
) -> ExtractionResult:
    """Extract structured data from contract text using a schema.

    Provide either schema_id or contract_type to select the schema.
    """
    if not request.schema_id and not request.contract_type:
        raise HTTPException(
            status_code=400,
            detail="Must provide either schema_id or contract_type"
        )

    try:
        result = await extract_with_schema(
            contract_text=request.contract_text,
            schema_id=request.schema_id,
            contract_type=request.contract_type,
            user_id=str(current_user.id),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract/{contract_id}", response_model=ExtractionResult)
async def extract_from_contract(
    contract_id: str,
    request: ExtractFromContractRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExtractionResult:
    """Extract structured data from an existing contract.

    If schema_id or contract_type is not provided, will attempt to
    auto-detect based on the contract's stored type.
    """
    from sqlalchemy import select
    import uuid

    # Get the contract
    try:
        contract_uuid = uuid.UUID(contract_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contract ID")

    result = await db.execute(
        select(Contract).where(Contract.id == contract_uuid)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get contract text
    if not contract.extracted_text:
        raise HTTPException(
            status_code=400,
            detail="Contract has no extracted text. Process the contract first."
        )

    # Determine schema to use
    schema_id = request.schema_id if request else None
    contract_type = request.contract_type if request else None

    # Auto-detect from contract type if not specified
    if not schema_id and not contract_type and contract.contract_type:
        contract_type = contract.contract_type

    if not schema_id and not contract_type:
        raise HTTPException(
            status_code=400,
            detail="Could not determine contract type. Provide schema_id or contract_type."
        )

    try:
        extraction_result = await extract_with_schema(
            contract_text=contract.extracted_text,
            schema_id=schema_id,
            contract_type=contract_type,
            contract_id=contract_id,
            user_id=str(current_user.id),
        )

        # Save extraction result to contract if requested
        should_save = request.save if request else True
        if should_save and extraction_result.extracted_data:
            contract.schema_data = extraction_result.extracted_data
            contract.schema_id = extraction_result.schema_id

            # Sync to relational structure (hybrid approach)
            from app.services.schema_sync import sync_schema_to_db
            await sync_schema_to_db(db, contract)

            await db.commit()

        return extraction_result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("/by-type/{contract_type}", response_model=SchemaDetailResponse | None)
async def get_schema_by_type(
    contract_type: str,
    current_user: User = Depends(get_current_user),
) -> SchemaDetailResponse | None:
    """Get schema for a contract type (MSA, SOW, NDA, etc.)."""
    registry = get_schema_registry()
    schema = registry.get_schema_for_contract_type(contract_type)

    if not schema:
        raise HTTPException(
            status_code=404,
            detail=f"No schema found for contract type: {contract_type}"
        )

    sections_dict = {}
    for name, section in schema.sections.items():
        sections_dict[name] = {
            "description": section.description,
            "priority": section.priority,
            "fields": {
                field_name: {
                    "type": field.type.value,
                    "description": field.description,
                    "required": field.required,
                }
                for field_name, field in section.fields.items()
            },
        }

    return SchemaDetailResponse(
        schema_id=schema.schema_id,
        contract_type=schema.contract_type,
        version=schema.version,
        description=schema.description,
        sections=sections_dict,
        extraction_model=schema.extraction_model,
        extraction_temperature=schema.extraction_temperature,
        max_tokens=schema.max_tokens,
        required_sections=schema.required_sections,
        json_template=schema.get_json_template(),
    )
