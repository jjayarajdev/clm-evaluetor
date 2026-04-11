"""Seed perception scores for all KPIs that don't have scores yet.

Creates realistic internal/external scores and perception gaps for demo purposes.
Run: cd backend && uv run python -m scripts.seed_perception_scores
"""

import asyncio
import random
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.kpi import (
    KPI,
    KPICategory,
    KPIMeasurementType,
    PerceptionGap,
    PerceptionScore,
)
from app.models.relationship import BusinessRelationship


# Score profiles by category — defines realistic ranges
# (internal_base, internal_variance, external_base, external_variance)
CATEGORY_PROFILES = {
    "service_delivery": (7.5, 1.0, 6.5, 1.2),
    "quality": (7.8, 0.8, 6.8, 1.0),
    "timeliness": (7.0, 1.2, 6.0, 1.5),
    "communication": (7.2, 1.0, 6.0, 1.3),
    "innovation": (6.5, 1.5, 5.5, 1.5),
    "cost_efficiency": (7.0, 1.0, 6.5, 1.2),
    "compliance": (8.0, 0.7, 7.5, 0.8),
    "satisfaction": (7.5, 1.0, 6.5, 1.2),
    "other": (7.0, 1.0, 6.0, 1.2),
}

PERIODS = ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"]


def generate_score(base: float, variance: float) -> float:
    """Generate a realistic score between 1-10."""
    score = random.gauss(base, variance)
    return round(max(1.0, min(10.0, score)), 2)


async def seed_scores():
    """Seed perception scores for all KPIs without existing scores."""
    async with async_session_maker() as session:
        # Find KPIs with no perception scores
        kpis_with_scores = (
            select(PerceptionScore.kpi_id).distinct()
        )
        result = await session.execute(
            select(KPI)
            .where(KPI.is_active == True)
            .where(KPI.id.notin_(kpis_with_scores))
        )
        kpis = result.scalars().all()

        if not kpis:
            print("All KPIs already have perception scores.")
            return

        print(f"Found {len(kpis)} KPIs without scores.")

        # Get relationship -> org mapping for scorer_org_id
        rel_ids = list(set(k.relationship_id for k in kpis))
        result = await session.execute(
            select(BusinessRelationship)
            .where(BusinessRelationship.id.in_(rel_ids))
        )
        relationships = {r.id: r for r in result.scalars().all()}

        scores_created = 0
        gaps_created = 0

        for kpi in kpis:
            rel = relationships.get(kpi.relationship_id)
            if not rel:
                print(f"  Skipping KPI {kpi.name}: relationship not found")
                continue

            internal_org_id = rel.org_a_id
            external_org_id = rel.org_b_id

            category = kpi.category or "other"
            profile = CATEGORY_PROFILES.get(category, CATEGORY_PROFILES["other"])
            int_base, int_var, ext_base, ext_var = profile

            # Generate scores for each period
            for period in PERIODS:
                # Add a slight trend improvement over time
                period_idx = PERIODS.index(period)
                trend = period_idx * 0.1

                int_score = generate_score(int_base + trend, int_var)
                ext_score = generate_score(ext_base + trend * 0.5, ext_var)

                # Internal score
                session.add(PerceptionScore(
                    id=uuid.uuid4(),
                    kpi_id=kpi.id,
                    scorer_org_id=internal_org_id,
                    score=Decimal(str(int_score)),
                    period=period,
                    is_internal=True,
                    approval_status="approved",
                    approved_at=datetime.utcnow(),
                    comments=None,
                ))

                # External score
                session.add(PerceptionScore(
                    id=uuid.uuid4(),
                    kpi_id=kpi.id,
                    scorer_org_id=external_org_id,
                    score=Decimal(str(ext_score)),
                    period=period,
                    is_internal=False,
                    approval_status="approved",
                    approved_at=datetime.utcnow(),
                    comments=None,
                ))
                scores_created += 2

            # Create perception gap for the latest period
            latest_period = PERIODS[-1]
            # Use the latest period scores for gap calculation
            int_latest = generate_score(int_base + len(PERIODS) * 0.1, int_var)
            ext_latest = generate_score(ext_base + len(PERIODS) * 0.05, ext_var)
            gap_value = round(int_latest - ext_latest, 2)
            severity = PerceptionGap.calculate_severity(Decimal(str(gap_value)))

            session.add(PerceptionGap(
                id=uuid.uuid4(),
                kpi_id=kpi.id,
                period=latest_period,
                internal_score=Decimal(str(int_latest)),
                external_score=Decimal(str(ext_latest)),
                gap=Decimal(str(gap_value)),
                gap_severity=severity,
                requires_action=severity in ("significant", "critical"),
            ))
            gaps_created += 1

        await session.commit()
        print(f"\nDone! Created {scores_created} perception scores and {gaps_created} perception gaps.")


if __name__ == "__main__":
    asyncio.run(seed_scores())
