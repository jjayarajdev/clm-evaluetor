"""Cascade-delete helpers for governance entities (relationships, organizations).

Extracted so the relationships endpoint, the organizations cascade-delete, and the
contract-delete orphan cleanup all share one correct ordering (there are no
DB-level cascades, so order matters). None of these commit — the caller does.
"""

from uuid import UUID

from sqlalchemy import delete as sa_delete, func, or_, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession


async def relationship_has_manual_data(db: AsyncSession, rel_id: UUID) -> bool:
    """True if a relationship carries user-entered governance data worth keeping:
    any perception scores, survey instances, or improvement points. KPIs
    auto-generated from a contract's SLAs (with no scores) do NOT count."""
    from app.models.kpi import KPI, PerceptionScore
    from app.models.improvement import ImprovementPoint
    from app.models.survey import SurveyInstance

    kpi_ids = select(KPI.id).where(KPI.relationship_id == rel_id)
    scores = (await db.execute(
        select(func.count(PerceptionScore.id)).where(PerceptionScore.kpi_id.in_(kpi_ids))
    )).scalar_one()
    surveys = (await db.execute(
        select(func.count(SurveyInstance.id)).where(SurveyInstance.relationship_id == rel_id)
    )).scalar_one()
    improvements = (await db.execute(
        select(func.count(ImprovementPoint.id)).where(ImprovementPoint.relationship_id == rel_id)
    )).scalar_one()
    return (scores + surveys + improvements) > 0


async def delete_relationship_cascade(db: AsyncSession, rel_id: UUID) -> None:
    """Delete a relationship and all its governance children (no commit).

    KPI scores/gaps -> KPIs, survey responses -> instances, improvement actions
    -> points, service links, team, history. Contracts and external access tokens
    are detached (relationship_id set NULL), never deleted. Organizations untouched.
    """
    from app.models.contract import Contract
    from app.models.external_access import ExternalAccessToken
    from app.models.improvement import ImprovementAction, ImprovementPoint
    from app.models.kpi import KPI, PerceptionGap, PerceptionScore
    from app.models.relationship import BusinessRelationship, RelationshipTeam
    from app.models.relationship_history import RelationshipStatusHistory
    from app.models.service_portfolio import RelationshipService
    from app.models.survey import SurveyInstance, SurveyQuestion, SurveyResponse

    kpi_ids = select(KPI.id).where(KPI.relationship_id == rel_id)
    instance_ids = select(SurveyInstance.id).where(SurveyInstance.relationship_id == rel_id)
    point_ids = select(ImprovementPoint.id).where(ImprovementPoint.relationship_id == rel_id)

    # KPI children
    await db.execute(sa_delete(PerceptionScore).where(PerceptionScore.kpi_id.in_(kpi_ids)))
    await db.execute(sa_delete(PerceptionGap).where(PerceptionGap.kpi_id.in_(kpi_ids)))
    # Tenant-level survey templates survive — detach their questions from these KPIs.
    await db.execute(
        sa_update(SurveyQuestion).where(SurveyQuestion.kpi_id.in_(kpi_ids)).values(kpi_id=None)
    )
    # Improvement points from OTHER relationships may reference these KPIs.
    await db.execute(
        sa_update(ImprovementPoint)
        .where(ImprovementPoint.kpi_id.in_(kpi_ids), ImprovementPoint.relationship_id != rel_id)
        .values(kpi_id=None)
    )

    # Surveys and improvements of this relationship
    await db.execute(sa_delete(SurveyResponse).where(SurveyResponse.survey_instance_id.in_(instance_ids)))
    await db.execute(sa_delete(ImprovementAction).where(ImprovementAction.improvement_id.in_(point_ids)))
    await db.execute(sa_delete(SurveyInstance).where(SurveyInstance.relationship_id == rel_id))
    await db.execute(sa_delete(ImprovementPoint).where(ImprovementPoint.relationship_id == rel_id))
    await db.execute(sa_delete(KPI).where(KPI.relationship_id == rel_id))

    # Structure around the relationship
    await db.execute(sa_delete(RelationshipService).where(RelationshipService.relationship_id == rel_id))
    await db.execute(sa_delete(RelationshipTeam).where(RelationshipTeam.relationship_id == rel_id))
    await db.execute(
        sa_delete(RelationshipStatusHistory).where(RelationshipStatusHistory.relationship_id == rel_id)
    )

    # Detach, never delete: contracts and external access tokens
    await db.execute(
        sa_update(Contract).where(Contract.business_relationship_id == rel_id).values(business_relationship_id=None)
    )
    await db.execute(
        sa_update(ExternalAccessToken).where(ExternalAccessToken.relationship_id == rel_id).values(relationship_id=None)
    )

    await db.execute(sa_delete(BusinessRelationship).where(BusinessRelationship.id == rel_id))


async def cleanup_orphaned_org_for_contract(db: AsyncSession, org_id: UUID) -> dict:
    """After a contract delete, remove the bridge-created org + relationship if the
    org is now orphaned (no contracts, no subsidiaries) and its relationships carry
    no manual governance data. Best-effort, no commit. Returns a summary.

    Relationships WITH manual data are preserved (so is the org), rather than
    silently wiping user-entered scores/surveys/improvements.
    """
    from app.models.contract import Contract
    from app.models.organization import Organization
    from app.models.organization_officer import OrganizationOfficer
    from app.models.relationship import BusinessRelationship

    summary = {"org_deleted": False, "relationships_deleted": 0, "kept_manual": False}

    remaining = (await db.execute(
        select(func.count(Contract.id)).where(Contract.organization_id == org_id)
    )).scalar_one()
    if remaining > 0:
        return summary  # org still in use by other contracts

    subsidiaries = (await db.execute(
        select(func.count(Organization.id)).where(Organization.parent_organization_id == org_id)
    )).scalar_one()
    if subsidiaries > 0:
        return summary  # part of a hierarchy — leave it

    rel_ids = [
        r for (r,) in (await db.execute(
            select(BusinessRelationship.id).where(
                or_(BusinessRelationship.org_a_id == org_id, BusinessRelationship.org_b_id == org_id)
            )
        )).all()
    ]
    for rid in rel_ids:
        if await relationship_has_manual_data(db, rid):
            summary["kept_manual"] = True
            return summary  # preserve everything; don't half-delete
        await delete_relationship_cascade(db, rid)
        summary["relationships_deleted"] += 1

    await db.execute(sa_delete(OrganizationOfficer).where(OrganizationOfficer.organization_id == org_id))
    await db.execute(sa_delete(Organization).where(Organization.id == org_id))
    summary["org_deleted"] = True
    return summary
