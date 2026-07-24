"""API endpoints for contract groups."""

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, RequiredTenantId, require_write
from app.database import get_db
from app.models import Contract, User
from app.models.contract_group import (
    ContractGroup,
    ContractGroupFinding,
    ContractGroupMember,
)
from app.schemas.contract_group import (
    FindingStatusUpdate,
    GroupCreate,
    GroupDetailResponse,
    GroupFindingResponse,
    GroupListResponse,
    GroupMemberAdd,
    GroupMemberContract,
    GroupResponse,
    GroupSummary,
    GroupUpdate,
)

router = APIRouter(prefix="/api/groups", tags=["Contract Groups"])


async def _get_group_or_404(
    db: AsyncSession, group_id: uuid.UUID, tenant_id: uuid.UUID
) -> ContractGroup:
    result = await db.execute(
        select(ContractGroup).where(
            ContractGroup.id == group_id,
            ContractGroup.tenant_id == tenant_id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return group


async def _get_descendant_group_ids(
    db: AsyncSession, group_id: uuid.UUID
) -> set[uuid.UUID]:
    """All descendant group IDs via recursive query (no ORM lazy loads)."""
    result = await db.execute(
        text("""
            WITH RECURSIVE descendants AS (
                SELECT id FROM contract_groups WHERE parent_group_id = :gid
                UNION ALL
                SELECT g.id FROM contract_groups g
                JOIN descendants d ON g.parent_group_id = d.id
            )
            SELECT id FROM descendants
        """),
        {"gid": group_id},
    )
    return {row[0] for row in result}


async def _member_counts(
    db: AsyncSession, group_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not group_ids:
        return {}
    result = await db.execute(
        select(ContractGroupMember.group_id, func.count(ContractGroupMember.id))
        .where(ContractGroupMember.group_id.in_(group_ids))
        .group_by(ContractGroupMember.group_id)
    )
    return dict(result.all())


async def _open_finding_counts(
    db: AsyncSession, group_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not group_ids:
        return {}
    result = await db.execute(
        select(ContractGroupFinding.group_id, func.count(ContractGroupFinding.id))
        .where(
            ContractGroupFinding.group_id.in_(group_ids),
            ContractGroupFinding.status == "open",
        )
        .group_by(ContractGroupFinding.group_id)
    )
    return dict(result.all())


def _group_to_response(
    group: ContractGroup,
    member_count: int = 0,
    open_finding_count: int = 0,
    owner_name: str | None = None,
    child_groups: list[GroupSummary] | None = None,
) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        tenant_id=group.tenant_id,
        name=group.name,
        description=group.description,
        group_type=group.group_type,
        parent_group_id=group.parent_group_id,
        owner_user_id=group.owner_user_id,
        owner_name=owner_name,
        root_contract_id=group.root_contract_id,
        upload_batch_id=group.upload_batch_id,
        member_count=member_count,
        open_finding_count=open_finding_count,
        child_groups=child_groups or [],
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.get("", response_model=GroupListResponse)
async def list_groups(
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    group_type: Optional[str] = Query(None),
    search: Optional[str] = None,
    parent_group_id: Optional[uuid.UUID] = Query(None),
) -> GroupListResponse:
    """List contract groups (paginated)."""
    query = select(ContractGroup).where(ContractGroup.tenant_id == tenant_id)
    if group_type:
        query = query.where(ContractGroup.group_type == group_type)
    if search:
        query = query.where(ContractGroup.name.ilike(f"%{search}%"))
    if parent_group_id:
        query = query.where(ContractGroup.parent_group_id == parent_group_id)

    total = (
        await db.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    query = (
        query.order_by(ContractGroup.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    groups = (await db.execute(query)).scalars().all()

    ids = [g.id for g in groups]
    counts = await _member_counts(db, ids)
    finding_counts = await _open_finding_counts(db, ids)

    return GroupListResponse(
        items=[
            _group_to_response(
                g,
                member_count=counts.get(g.id, 0),
                open_finding_count=finding_counts.get(g.id, 0),
            )
            for g in groups
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total else 0,
    )


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_write)])
async def create_group(
    data: GroupCreate,
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupResponse:
    """Create a manual contract group."""
    if data.parent_group_id:
        await _get_group_or_404(db, data.parent_group_id, tenant_id)
    if data.owner_user_id:
        owner = (
            await db.execute(
                select(User).where(
                    User.id == data.owner_user_id, User.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner user not found",
            )

    group = ContractGroup(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        group_type="manual",
        parent_group_id=data.parent_group_id,
        owner_user_id=data.owner_user_id,
        created_by_user_id=current_user.id,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return _group_to_response(group)


@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group(
    group_id: uuid.UUID,
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupDetailResponse:
    """Group detail with member contracts, findings, and child groups."""
    group = await _get_group_or_404(db, group_id, tenant_id)

    member_rows = (
        await db.execute(
            select(ContractGroupMember, Contract)
            .join(Contract, ContractGroupMember.contract_id == Contract.id)
            .where(ContractGroupMember.group_id == group_id)
            .order_by(Contract.filename)
        )
    ).all()

    members = [
        GroupMemberContract(
            contract_id=c.id,
            filename=c.filename,
            contract_type=c.contract_type,
            counterparty=c.counterparty,
            status=c.status.value if hasattr(c.status, "value") else c.status,
            risk_level=(
                c.risk_level.value if hasattr(c.risk_level, "value") else c.risk_level
            ),
            expiration_date=str(c.expiration_date) if c.expiration_date else None,
            source=m.source,
            member_id=m.id,
        )
        for m, c in member_rows
    ]

    finding_rows = (
        await db.execute(
            select(ContractGroupFinding, Contract.filename)
            .join(Contract, ContractGroupFinding.contract_id == Contract.id)
            .where(ContractGroupFinding.group_id == group_id)
            .order_by(ContractGroupFinding.status, ContractGroupFinding.reference_label)
        )
    ).all()
    findings = [f for f, _ in finding_rows]
    finding_filenames = {f.id: fn for f, fn in finding_rows}

    children = (
        (
            await db.execute(
                select(ContractGroup).where(
                    ContractGroup.parent_group_id == group_id,
                    ContractGroup.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    child_counts = await _member_counts(db, [c.id for c in children])

    owner_name = None
    if group.owner_user_id:
        owner = (
            await db.execute(select(User).where(User.id == group.owner_user_id))
        ).scalar_one_or_none()
        owner_name = owner.full_name or owner.username if owner else None

    base = _group_to_response(
        group,
        member_count=len(members),
        open_finding_count=sum(1 for f in findings if f.status == "open"),
        owner_name=owner_name,
        child_groups=[
            GroupSummary(
                id=c.id,
                name=c.name,
                group_type=c.group_type,
                parent_group_id=c.parent_group_id,
                owner_user_id=c.owner_user_id,
                member_count=child_counts.get(c.id, 0),
            )
            for c in children
        ],
    )
    finding_responses = []
    for f in findings:
        fr = GroupFindingResponse.model_validate(f)
        fr.contract_filename = finding_filenames.get(f.id)
        finding_responses.append(fr)

    return GroupDetailResponse(
        **base.model_dump(),
        members=members,
        findings=finding_responses,
    )


@router.patch("/{group_id}", response_model=GroupResponse,
              dependencies=[Depends(require_write)])
async def update_group(
    group_id: uuid.UUID,
    data: GroupUpdate,
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupResponse:
    """Update group name/description/nesting/owner."""
    group = await _get_group_or_404(db, group_id, tenant_id)

    if data.parent_group_id is not None and data.parent_group_id != group.parent_group_id:
        if data.parent_group_id == group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group cannot be its own parent",
            )
        await _get_group_or_404(db, data.parent_group_id, tenant_id)
        if data.parent_group_id in await _get_descendant_group_ids(db, group_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot nest a group under its own descendant",
            )

    if data.owner_user_id is not None:
        owner = (
            await db.execute(
                select(User).where(
                    User.id == data.owner_user_id, User.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if not owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner user not found",
            )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(group, field, value)

    await db.commit()
    await db.refresh(group)
    counts = await _member_counts(db, [group.id])
    return _group_to_response(group, member_count=counts.get(group.id, 0))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_write)])
async def delete_group(
    group_id: uuid.UUID,
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a group. Members cascade; contracts are unaffected."""
    group = await _get_group_or_404(db, group_id, tenant_id)
    await db.delete(group)
    await db.commit()


@router.post("/{group_id}/members", response_model=GroupDetailResponse,
             dependencies=[Depends(require_write)])
async def add_members(
    group_id: uuid.UUID,
    data: GroupMemberAdd,
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupDetailResponse:
    """Add contracts to a group (idempotent for existing members)."""
    group = await _get_group_or_404(db, group_id, tenant_id)

    contracts = (
        (
            await db.execute(
                select(Contract.id).where(
                    Contract.id.in_(data.contract_ids),
                    Contract.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if len(contracts) != len(set(data.contract_ids)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more contracts not found",
        )

    existing = set(
        (
            await db.execute(
                select(ContractGroupMember.contract_id).where(
                    ContractGroupMember.group_id == group_id
                )
            )
        )
        .scalars()
        .all()
    )
    for cid in contracts:
        if cid not in existing:
            db.add(
                ContractGroupMember(
                    tenant_id=tenant_id,
                    group_id=group_id,
                    contract_id=cid,
                    source="manual",
                    added_by_user_id=current_user.id,
                )
            )
    await db.commit()
    return await get_group(group_id, tenant_id, current_user, db)


@router.patch("/{group_id}/findings/{finding_id}", response_model=GroupFindingResponse,
              dependencies=[Depends(require_write)])
async def update_finding_status(
    group_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: FindingStatusUpdate,
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupFindingResponse:
    """Dismiss or re-open a missing-reference finding."""
    await _get_group_or_404(db, group_id, tenant_id)
    finding = (
        await db.execute(
            select(ContractGroupFinding).where(
                ContractGroupFinding.id == finding_id,
                ContractGroupFinding.tenant_id == tenant_id,
                ContractGroupFinding.group_id == group_id,
            )
        )
    ).scalar_one_or_none()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    finding.status = body.status
    finding.dismissed_by_user_id = (
        current_user.id if body.status == "dismissed" else None
    )
    if body.status == "open":
        finding.resolved_by_contract_id = None
    await db.commit()
    await db.refresh(finding)
    return GroupFindingResponse.model_validate(finding)


@router.delete("/{group_id}/members/{contract_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_write)])
async def remove_member(
    group_id: uuid.UUID,
    contract_id: uuid.UUID,
    tenant_id: RequiredTenantId,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a contract from a group."""
    await _get_group_or_404(db, group_id, tenant_id)
    member = (
        await db.execute(
            select(ContractGroupMember).where(
                ContractGroupMember.group_id == group_id,
                ContractGroupMember.contract_id == contract_id,
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )
    await db.delete(member)
    await db.commit()
