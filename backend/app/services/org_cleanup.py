"""Safe organization deletion with full governance cascade.

An organization is referenced by business relationships and everything that
hangs off them (KPIs, perception scores/gaps, surveys, improvements, teams,
history, service portfolios, access tokens). Deleting an org therefore means
deleting that whole subtree in dependency order. Used when family inheritance
vacates a junk org, and by the reconcile tooling.
"""

import logging
import uuid

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.organization import Organization

logger = logging.getLogger(__name__)


async def prune_unreliable_orgs(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Remove organizations mistakenly minted from a non-organization counterparty
    (a document title like "Exhibits", a placeholder like "PST will be agreed").

    Detaches their contracts (organization_id -> NULL; the raw counterparty text
    is untouched) then deletes the now-empty org, so the Vendors and
    Organizations views agree — neither shows a junk party. Real names and
    genuinely-ambiguous fragments (e.g. "2IM") are left alone. No commit.
    """
    from app.agents.metadata_extraction import is_unreliable_counterparty

    orgs = (
        (await db.execute(select(Organization).where(Organization.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    pruned = 0
    for org in orgs:
        if not is_unreliable_counterparty(org.name):
            continue
        await db.execute(
            update(Contract)
            .where(Contract.organization_id == org.id)
            .values(organization_id=None)
        )
        await db.flush()
        if await prune_org_if_empty(db, org.id):
            pruned += 1
    if pruned:
        logger.info(f"Pruned {pruned} non-organization org(s) for tenant {tenant_id}")
        await db.flush()
    return pruned


async def _org_contract_count(db: AsyncSession, org_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count()).where(Contract.organization_id == org_id)
        )
    ).scalar() or 0


async def delete_org_cascade(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Delete an organization and its entire governance subtree. No commit."""
    p = {"oid": str(org_id)}
    rel_ids = [
        str(r)
        for (r,) in (
            await db.execute(
                text(
                    "SELECT id FROM business_relationships "
                    "WHERE org_a_id = :oid OR org_b_id = :oid"
                ),
                p,
            )
        ).all()
    ]
    kpi_ids: list[str] = []
    inst_ids: list[str] = []
    if rel_ids:
        kpi_ids = [
            str(r)
            for (r,) in (
                await db.execute(
                    text("SELECT id FROM kpis WHERE relationship_id = ANY(:rids)"),
                    {"rids": rel_ids},
                )
            ).all()
        ]
        inst_ids = [
            str(r)
            for (r,) in (
                await db.execute(
                    text(
                        "SELECT id FROM survey_instances "
                        "WHERE relationship_id = ANY(:rids)"
                    ),
                    {"rids": rel_ids},
                )
            ).all()
        ]

    if kpi_ids:
        await db.execute(text("DELETE FROM perception_scores WHERE kpi_id = ANY(:v)"), {"v": kpi_ids})
        await db.execute(text("DELETE FROM perception_gaps WHERE kpi_id = ANY(:v)"), {"v": kpi_ids})
        await db.execute(text("UPDATE survey_questions SET kpi_id = NULL WHERE kpi_id = ANY(:v)"), {"v": kpi_ids})
    await db.execute(text("DELETE FROM perception_scores WHERE scorer_org_id = :oid"), p)
    if inst_ids:
        await db.execute(text("DELETE FROM survey_responses WHERE survey_instance_id = ANY(:v)"), {"v": inst_ids})
        await db.execute(text("DELETE FROM external_access_tokens WHERE survey_instance_id = ANY(:v)"), {"v": inst_ids})
    if rel_ids:
        await db.execute(text("DELETE FROM external_access_tokens WHERE relationship_id = ANY(:v)"), {"v": rel_ids})
        await db.execute(
            text(
                "DELETE FROM improvement_actions WHERE improvement_id IN "
                "(SELECT id FROM improvement_points WHERE relationship_id = ANY(:v))"
            ),
            {"v": rel_ids},
        )
        await db.execute(text("DELETE FROM improvement_points WHERE relationship_id = ANY(:v)"), {"v": rel_ids})
        await db.execute(text("DELETE FROM survey_instances WHERE relationship_id = ANY(:v)"), {"v": rel_ids})
        await db.execute(text("DELETE FROM kpis WHERE relationship_id = ANY(:v)"), {"v": rel_ids})
        await db.execute(text("DELETE FROM relationship_teams WHERE relationship_id = ANY(:v)"), {"v": rel_ids})
        await db.execute(text("DELETE FROM relationship_status_history WHERE relationship_id = ANY(:v)"), {"v": rel_ids})
        await db.execute(text("DELETE FROM relationship_services WHERE relationship_id = ANY(:v)"), {"v": rel_ids})
    await db.execute(text("DELETE FROM external_access_tokens WHERE organization_id = :oid"), p)
    await db.execute(text("UPDATE improvement_points SET assigned_org_id = NULL WHERE assigned_org_id = :oid"), p)
    await db.execute(text("DELETE FROM service_portfolios WHERE organization_id = :oid"), p)
    await db.execute(text("DELETE FROM organization_officers WHERE organization_id = :oid"), p)
    await db.execute(text("DELETE FROM external_users WHERE organization_id = :oid"), p)
    if rel_ids:
        await db.execute(text("UPDATE contracts SET business_relationship_id = NULL WHERE business_relationship_id = ANY(:v)"), {"v": rel_ids})
        await db.execute(text("DELETE FROM business_relationships WHERE id = ANY(:v)"), {"v": rel_ids})
    await db.execute(text("DELETE FROM organizations WHERE id = :oid"), p)


async def prune_org_if_empty(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """Delete an org (cascade) only if it currently has zero contracts.

    Returns True if it was deleted. Guards against removing an org that still
    holds contracts. No commit.
    """
    if await _org_contract_count(db, org_id) > 0:
        return False
    org = await db.get(Organization, org_id)
    if not org:
        return False
    name = org.name
    await delete_org_cascade(db, org_id)
    logger.info(f"Pruned emptied organization '{name}' ({org_id})")
    return True
