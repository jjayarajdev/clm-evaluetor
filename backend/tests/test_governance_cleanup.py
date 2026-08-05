"""Orphaned-org cleanup + cascade delete (2026-08-05).

- Deleting an org's last contract removes the bridge-created org + relationship,
  UNLESS the relationship carries manual governance data (perception scores etc).
- Org hard-delete with cascade removes the org's relationships first.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.models.tenant import Tenant
from app.models.organization import Organization
from app.models.relationship import BusinessRelationship
from app.models.kpi import KPI, PerceptionScore
from app.services.governance_cleanup import (
    cleanup_orphaned_org_for_contract,
    delete_relationship_cascade,
    relationship_has_manual_data,
)

TID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest_asyncio.fixture(scope="function")
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _pragma(conn, rec):
        cur = conn.cursor(); cur.execute("PRAGMA foreign_keys=OFF"); cur.close()

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    seen = set()
    for table in Base.metadata.tables.values():
        deduped = [i for i in table.indexes if i.name not in seen and not seen.add(i.name)]
        table.indexes.clear(); table.indexes.update(deduped)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await eng.dispose()


async def _internal_and_vendor(db, *, with_score=False):
    """Internal org + a vendor org joined by a relationship (with a KPI, and
    optionally a manual perception score)."""
    if not await db.get(Tenant, TID):
        db.add(Tenant(id=TID, name="T", slug="t", is_active=True))
        await db.flush()
    sfx = uuid.uuid4().hex[:6]
    internal = Organization(id=uuid.uuid4(), tenant_id=TID, name="Us", code=f"US{sfx}", org_type="internal", is_active=True)
    vendor = Organization(id=uuid.uuid4(), tenant_id=TID, name="Vendor", code=f"V{sfx}", org_type="vendor", is_active=True)
    db.add_all([internal, vendor])
    await db.flush()
    rel = BusinessRelationship(
        id=uuid.uuid4(), tenant_id=TID, org_a_id=internal.id, org_b_id=vendor.id,
        relationship_type="supplier", status="active",
    )
    db.add(rel)
    await db.flush()
    kpi = KPI(id=uuid.uuid4(), relationship_id=rel.id, name="Uptime", category="service_delivery")
    db.add(kpi)
    await db.flush()
    if with_score:
        db.add(PerceptionScore(
            id=uuid.uuid4(), kpi_id=kpi.id, scorer_org_id=vendor.id,
            score=8, period="2026-Q1", is_internal=True,
        ))
        await db.flush()
    return internal, vendor, rel


@pytest.mark.asyncio
async def test_orphan_cleanup_removes_org_and_relationship(db):
    internal, vendor, rel = await _internal_and_vendor(db)
    # Vendor has no contracts → orphaned → cleaned up.
    summary = await cleanup_orphaned_org_for_contract(db, vendor.id)
    assert summary["org_deleted"] is True
    assert summary["relationships_deleted"] == 1
    assert (await db.execute(select(func.count(Organization.id)).where(Organization.id == vendor.id))).scalar_one() == 0
    assert (await db.execute(select(func.count(BusinessRelationship.id)).where(BusinessRelationship.id == rel.id))).scalar_one() == 0
    # The internal org is NOT deleted (it's the other party, not the orphan target).
    assert (await db.execute(select(func.count(Organization.id)).where(Organization.id == internal.id))).scalar_one() == 1


@pytest.mark.asyncio
async def test_orphan_cleanup_preserves_manual_governance_data(db):
    internal, vendor, rel = await _internal_and_vendor(db, with_score=True)
    summary = await cleanup_orphaned_org_for_contract(db, vendor.id)
    assert summary["kept_manual"] is True
    assert summary["org_deleted"] is False
    # Everything preserved.
    assert (await db.execute(select(func.count(Organization.id)).where(Organization.id == vendor.id))).scalar_one() == 1
    assert (await db.execute(select(func.count(BusinessRelationship.id)).where(BusinessRelationship.id == rel.id))).scalar_one() == 1


@pytest.mark.asyncio
async def test_relationship_has_manual_data(db):
    _, _, rel_clean = await _internal_and_vendor(db)
    assert await relationship_has_manual_data(db, rel_clean.id) is False
    _, _, rel_scored = await _internal_and_vendor(db, with_score=True)
    assert await relationship_has_manual_data(db, rel_scored.id) is True


@pytest.mark.asyncio
async def test_cascade_delete_removes_relationship_children(db):
    _, _, rel = await _internal_and_vendor(db, with_score=True)
    await delete_relationship_cascade(db, rel.id)
    assert (await db.execute(select(func.count(BusinessRelationship.id)).where(BusinessRelationship.id == rel.id))).scalar_one() == 0
    assert (await db.execute(select(func.count(KPI.id)).where(KPI.relationship_id == rel.id))).scalar_one() == 0
