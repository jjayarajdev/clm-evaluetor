"""Business-unit visibility for governance data (orgs, relationships, children).

Contracts carry a business_unit_id and are BU-filtered everywhere via
core.tenant.apply_bu_filter. Organizations and BusinessRelationships are
deliberately SHARED per-tenant entities (one org per counterparty — "Vendors ==
Organizations by construction"), so they must not be BU-tagged. Instead their
visibility is DERIVED from the contracts that link to them:

    visible ⇔ the user can see at least one contract linking to the entity,
              OR the entity has no linked contracts at all (tenant-shared,
              mirroring the "NULL BU = unassigned = visible to all" rule).

Escape hatches mirror apply_bu_filter byte-for-byte: super_admin and users
with no BU are unrestricted; bu_head sees their BU subtree; other roles see
their own BU only.

Trap to keep in mind: the tenant's own internal org never has contracts
pointing at it (contracts.organization_id is always the counterparty), so the
relationship fallback ANDs both org sides — an OR would make every
relationship visible through the internal side.
"""

from __future__ import annotations

import uuid

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def _all_child_bu_ids(db: AsyncSession, bu_id: uuid.UUID) -> list[uuid.UUID]:
    """All descendant BU ids (recursive), same semantics as contracts.py."""
    from app.models.business_unit import BusinessUnit

    children = (
        await db.execute(select(BusinessUnit.id).where(BusinessUnit.parent_id == bu_id))
    ).scalars().all()
    all_ids: list[uuid.UUID] = []
    for child_id in children:
        all_ids.append(child_id)
        all_ids.extend(await _all_child_bu_ids(db, child_id))
    return all_ids


async def resolve_visible_bu_ids(db: AsyncSession, user) -> list[uuid.UUID] | None:
    """The BU ids this user may see, or None for unrestricted.

    None => super_admin, or a user with no BU (tenant-wide access).
    bu_head => own BU + all descendants. Everyone else => own BU only.
    """
    if user is None or user.business_unit_id is None:
        return None
    role = user.role.value if user.role else None
    if role == "super_admin":
        return None
    ids = [user.business_unit_id]
    if role == "bu_head":
        ids.extend(await _all_child_bu_ids(db, user.business_unit_id))
    return ids


def _org_contracts_visible(org_id_col, visible_bu_ids: list[uuid.UUID]):
    """Org-side visibility, correlated on an arbitrary org-id column:
    the org has NO contracts at all, OR at least one contract in a visible
    BU / with no BU."""
    from app.models.contract import Contract

    any_contract = exists(select(1).where(Contract.organization_id == org_id_col))
    visible_contract = exists(
        select(1).where(
            and_(
                Contract.organization_id == org_id_col,
                or_(
                    Contract.business_unit_id.in_(visible_bu_ids),
                    Contract.business_unit_id.is_(None),
                ),
            )
        )
    )
    return or_(~any_contract, visible_contract)


def org_bu_visibility_clause(visible_bu_ids: list[uuid.UUID] | None):
    """Boolean clause for queries selecting Organization. None => unrestricted."""
    if visible_bu_ids is None:
        return None
    from app.models.organization import Organization

    return _org_contracts_visible(Organization.id, visible_bu_ids)


def relationship_bu_visibility_clause(visible_bu_ids: list[uuid.UUID] | None):
    """Boolean clause for queries selecting BusinessRelationship."""
    if visible_bu_ids is None:
        return None
    from app.models.contract import Contract
    from app.models.relationship import BusinessRelationship as BR

    any_direct = exists(select(1).where(Contract.business_relationship_id == BR.id))
    visible_direct = exists(
        select(1).where(
            and_(
                Contract.business_relationship_id == BR.id,
                or_(
                    Contract.business_unit_id.in_(visible_bu_ids),
                    Contract.business_unit_id.is_(None),
                ),
            )
        )
    )
    # No directly-linked contracts: BOTH org sides must pass the org rule
    # (AND — the internal org always passes since contracts never point at
    # it; the counterparty side decides, whichever side it sits on).
    return or_(
        visible_direct,
        and_(
            ~any_direct,
            _org_contracts_visible(BR.org_a_id, visible_bu_ids),
            _org_contracts_visible(BR.org_b_id, visible_bu_ids),
        ),
    )


def visible_relationship_ids_subquery(tenant_id, visible_bu_ids: list[uuid.UUID] | None):
    """select(BR.id) filtered by tenant + BU visibility — for children keyed
    by relationship_id where a join is inconvenient."""
    from app.models.relationship import BusinessRelationship as BR

    query = select(BR.id)
    if tenant_id is not None:
        query = query.where(BR.tenant_id == tenant_id)
    clause = relationship_bu_visibility_clause(visible_bu_ids)
    if clause is not None:
        query = query.where(clause)
    return query
