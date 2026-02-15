"""Clients router for managing client organizations."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Client, Contract
from app.routers.auth import CurrentUser

router = APIRouter(prefix="/api/clients", tags=["Clients"])


# ============ Pydantic Schemas ============


class ClientCreate(BaseModel):
    """Schema for creating a client."""

    name: str = Field(..., min_length=1, max_length=255, description="Full client name")
    code: str = Field(..., min_length=1, max_length=50, description="Short code for folder naming")

    # Optional fields
    industry: str | None = Field(None, max_length=100)
    website: str | None = Field(None, max_length=255)
    address: str | None = None
    city: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    contact_name: str | None = Field(None, max_length=255)
    contact_email: str | None = Field(None, max_length=255)
    contact_phone: str | None = Field(None, max_length=50)
    contact_title: str | None = Field(None, max_length=100)
    notes: str | None = None


class ClientUpdate(BaseModel):
    """Schema for updating a client."""

    name: str | None = Field(None, min_length=1, max_length=255)
    code: str | None = Field(None, min_length=1, max_length=50)
    industry: str | None = Field(None, max_length=100)
    website: str | None = Field(None, max_length=255)
    address: str | None = None
    city: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    contact_name: str | None = Field(None, max_length=255)
    contact_email: str | None = Field(None, max_length=255)
    contact_phone: str | None = Field(None, max_length=50)
    contact_title: str | None = Field(None, max_length=100)
    notes: str | None = None


class ClientResponse(BaseModel):
    """Schema for client response."""

    id: str
    name: str
    code: str
    industry: str | None
    website: str | None
    address: str | None
    city: str | None
    country: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    contact_title: str | None
    notes: str | None
    contract_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ClientListResponse(BaseModel):
    """Schema for paginated client list."""

    clients: list[ClientResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ClientSummary(BaseModel):
    """Brief client info for dropdowns."""

    id: str
    name: str
    code: str
    contract_count: int


# ============ Helper Functions ============


def client_to_response(client: Client, contract_count: int = 0) -> ClientResponse:
    """Convert Client model to response schema."""
    return ClientResponse(
        id=str(client.id),
        name=client.name,
        code=client.code,
        industry=client.industry,
        website=client.website,
        address=client.address,
        city=client.city,
        country=client.country,
        contact_name=client.contact_name,
        contact_email=client.contact_email,
        contact_phone=client.contact_phone,
        contact_title=client.contact_title,
        notes=client.notes,
        contract_count=contract_count,
        created_at=client.created_at.isoformat(),
        updated_at=client.updated_at.isoformat(),
    )


# ============ Endpoints ============


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    data: ClientCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClientResponse:
    """Create a new client.

    Args:
        data: Client data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Created client.
    """
    # Check if code already exists
    existing = await db.execute(
        select(Client).where(func.lower(Client.code) == data.code.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Client with code '{data.code}' already exists",
        )

    # Create client
    client = Client(
        name=data.name,
        code=data.code.upper(),  # Normalize code to uppercase
        industry=data.industry,
        website=data.website,
        address=data.address,
        city=data.city,
        country=data.country,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        contact_title=data.contact_title,
        notes=data.notes,
    )

    db.add(client)
    await db.commit()
    await db.refresh(client)

    return client_to_response(client, 0)


@router.get("", response_model=ClientListResponse)
async def list_clients(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
) -> ClientListResponse:
    """List all clients with pagination.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number (1-indexed).
        page_size: Items per page.
        search: Optional search term for name or code.

    Returns:
        Paginated list of clients.
    """
    # Base query
    query = select(Client)

    # Apply search filter
    if search:
        search_filter = (
            Client.name.ilike(f"%{search}%") |
            Client.code.ilike(f"%{search}%")
        )
        query = query.where(search_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Client.name).offset(offset).limit(page_size)

    result = await db.execute(query)
    clients = result.scalars().all()

    # Get contract counts for each client
    client_responses = []
    for client in clients:
        count_result = await db.execute(
            select(func.count()).select_from(Contract).where(Contract.client_id == client.id)
        )
        contract_count = count_result.scalar() or 0
        client_responses.append(client_to_response(client, contract_count))

    total_pages = (total + page_size - 1) // page_size

    return ClientListResponse(
        clients=client_responses,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/summary", response_model=list[ClientSummary])
async def list_clients_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ClientSummary]:
    """Get a brief list of all clients for dropdowns.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        List of client summaries.
    """
    # Get all clients with contract counts
    query = (
        select(
            Client.id,
            Client.name,
            Client.code,
            func.count(Contract.id).label("contract_count"),
        )
        .outerjoin(Contract, Contract.client_id == Client.id)
        .group_by(Client.id)
        .order_by(Client.name)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        ClientSummary(
            id=str(row.id),
            name=row.name,
            code=row.code,
            contract_count=row.contract_count or 0,
        )
        for row in rows
    ]


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClientResponse:
    """Get a client by ID.

    Args:
        client_id: Client ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Client details.
    """
    result = await db.execute(
        select(Client).where(Client.id == uuid.UUID(client_id))
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client not found: {client_id}",
        )

    # Get contract count
    count_result = await db.execute(
        select(func.count()).select_from(Contract).where(Contract.client_id == client.id)
    )
    contract_count = count_result.scalar() or 0

    return client_to_response(client, contract_count)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    data: ClientUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClientResponse:
    """Update a client.

    Args:
        client_id: Client ID.
        data: Updated client data.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated client.
    """
    result = await db.execute(
        select(Client).where(Client.id == uuid.UUID(client_id))
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client not found: {client_id}",
        )

    # Check if new code conflicts with existing
    if data.code and data.code.upper() != client.code:
        existing = await db.execute(
            select(Client).where(
                func.lower(Client.code) == data.code.lower(),
                Client.id != client.id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Client with code '{data.code}' already exists",
            )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "code" and value:
            value = value.upper()
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)

    # Get contract count
    count_result = await db.execute(
        select(func.count()).select_from(Contract).where(Contract.client_id == client.id)
    )
    contract_count = count_result.scalar() or 0

    return client_to_response(client, contract_count)


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    force: bool = Query(False, description="Force delete even if client has contracts"),
) -> dict:
    """Delete a client.

    Args:
        client_id: Client ID.
        current_user: Authenticated user.
        db: Database session.
        force: If True, unlink contracts before deleting.

    Returns:
        Confirmation message.
    """
    result = await db.execute(
        select(Client).where(Client.id == uuid.UUID(client_id))
    )
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client not found: {client_id}",
        )

    # Check if client has contracts
    count_result = await db.execute(
        select(func.count()).select_from(Contract).where(Contract.client_id == client.id)
    )
    contract_count = count_result.scalar() or 0

    if contract_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Client has {contract_count} contracts. Use force=true to unlink and delete.",
        )

    # Unlink contracts if force delete
    if contract_count > 0:
        from sqlalchemy import update
        await db.execute(
            update(Contract).where(Contract.client_id == client.id).values(client_id=None)
        )

    # Delete client
    await db.delete(client)
    await db.commit()

    return {
        "message": "Client deleted successfully",
        "client_id": client_id,
        "contracts_unlinked": contract_count if force else 0,
    }
