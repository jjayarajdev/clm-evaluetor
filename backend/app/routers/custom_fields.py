"""Custom Fields admin API for tenant-specific field definitions."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser, RequiredTenantId
from app.database import get_db
from app.models.tenant import Tenant
from app.schemas.custom_fields import (
    CustomFieldCreate,
    CustomFieldDefinition,
    CustomFieldResponse,
    CustomFieldsListResponse,
    CustomFieldUpdate,
    EntityType,
)

router = APIRouter(prefix="/api/admin/custom-fields", tags=["Custom Fields"])


def _get_field_definitions(tenant: Tenant, entity_type: str) -> list[dict]:
    """Get field definitions for an entity type."""
    definitions = tenant.custom_field_definitions or {}
    return definitions.get(entity_type, [])


def _set_field_definitions(tenant: Tenant, entity_type: str, fields: list[dict]) -> None:
    """Set field definitions for an entity type."""
    definitions = dict(tenant.custom_field_definitions or {})
    definitions[entity_type] = fields
    tenant.custom_field_definitions = definitions


@router.get("/{entity_type}", response_model=CustomFieldsListResponse)
async def list_custom_fields(
    entity_type: EntityType,
    tenant_id: RequiredTenantId,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomFieldsListResponse:
    """List all custom fields for an entity type.

    Returns the custom field definitions configured for this tenant.
    """
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    fields = _get_field_definitions(tenant, entity_type.value)

    return CustomFieldsListResponse(
        entity_type=entity_type,
        fields=[CustomFieldResponse(**f) for f in fields],
    )


@router.post("/{entity_type}", response_model=CustomFieldResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_field(
    entity_type: EntityType,
    data: CustomFieldCreate,
    tenant_id: RequiredTenantId,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomFieldResponse:
    """Create a new custom field for an entity type.

    The field will be available for all records of this entity type
    within the tenant.
    """
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    fields = _get_field_definitions(tenant, entity_type.value)

    # Check for duplicate field name
    if any(f["name"] == data.field.name for f in fields):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field '{data.field.name}' already exists for {entity_type.value}",
        )

    # Validate dropdown/multi_select have options
    if data.field.field_type in ("dropdown", "multi_select") and not data.field.options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field type '{data.field.field_type}' requires options",
        )

    # Add field with display_order
    new_field = data.field.model_dump()
    if new_field["display_order"] == 0:
        # Auto-assign display order if not specified
        max_order = max((f.get("display_order", 0) for f in fields), default=0)
        new_field["display_order"] = max_order + 1

    fields.append(new_field)
    _set_field_definitions(tenant, entity_type.value, fields)

    await db.commit()

    return CustomFieldResponse(**new_field)


@router.get("/{entity_type}/{field_name}", response_model=CustomFieldResponse)
async def get_custom_field(
    entity_type: EntityType,
    field_name: str,
    tenant_id: RequiredTenantId,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomFieldResponse:
    """Get a specific custom field definition."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    fields = _get_field_definitions(tenant, entity_type.value)
    field = next((f for f in fields if f["name"] == field_name), None)

    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_name}' not found for {entity_type.value}",
        )

    return CustomFieldResponse(**field)


@router.put("/{entity_type}/{field_name}", response_model=CustomFieldResponse)
async def update_custom_field(
    entity_type: EntityType,
    field_name: str,
    data: CustomFieldUpdate,
    tenant_id: RequiredTenantId,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomFieldResponse:
    """Update a custom field definition.

    Note: Changing field_type is not allowed as it could invalidate
    existing data. Create a new field instead.
    """
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    fields = _get_field_definitions(tenant, entity_type.value)
    field_index = next((i for i, f in enumerate(fields) if f["name"] == field_name), None)

    if field_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_name}' not found for {entity_type.value}",
        )

    # Update only provided fields
    current_field = fields[field_index]
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        current_field[key] = value

    fields[field_index] = current_field
    _set_field_definitions(tenant, entity_type.value, fields)

    await db.commit()

    return CustomFieldResponse(**current_field)


@router.delete("/{entity_type}/{field_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_field(
    entity_type: EntityType,
    field_name: str,
    tenant_id: RequiredTenantId,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    hard_delete: bool = False,
) -> None:
    """Delete a custom field definition.

    By default, this archives the field (marks as deleted but keeps the definition).
    Use hard_delete=true to permanently remove the field definition.

    Note: Existing field values in records are NOT deleted. They will be
    ignored but remain in the database for data recovery purposes.
    """
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    fields = _get_field_definitions(tenant, entity_type.value)
    field_index = next((i for i, f in enumerate(fields) if f["name"] == field_name), None)

    if field_index is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_name}' not found for {entity_type.value}",
        )

    if hard_delete:
        # Permanently remove the field definition
        fields.pop(field_index)
    else:
        # Soft delete - mark as archived
        fields[field_index]["is_archived"] = True
        fields[field_index]["is_visible"] = False

    _set_field_definitions(tenant, entity_type.value, fields)

    await db.commit()


@router.post("/{entity_type}/reorder")
async def reorder_custom_fields(
    entity_type: EntityType,
    field_order: list[str],
    tenant_id: RequiredTenantId,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CustomFieldsListResponse:
    """Reorder custom fields by providing the new order of field names.

    Args:
        field_order: List of field names in desired order.
    """
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    fields = _get_field_definitions(tenant, entity_type.value)
    field_map = {f["name"]: f for f in fields}

    # Validate all field names exist
    for name in field_order:
        if name not in field_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown field: {name}",
            )

    # Reorder fields
    reordered = []
    for i, name in enumerate(field_order):
        field = field_map[name]
        field["display_order"] = i + 1
        reordered.append(field)

    # Add any fields not in the order list at the end
    for name, field in field_map.items():
        if name not in field_order:
            field["display_order"] = len(reordered) + 1
            reordered.append(field)

    _set_field_definitions(tenant, entity_type.value, reordered)

    await db.commit()

    return CustomFieldsListResponse(
        entity_type=entity_type,
        fields=[CustomFieldResponse(**f) for f in reordered],
    )
