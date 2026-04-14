"""KPI scoring and gap recalculation workflow tests.

Tests service functions directly (not via HTTP) to verify
perception score aggregation, gap calculation, and response mapping.
"""

import pytest
import pytest_asyncio
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import event, select, JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.models.tenant import Tenant
from app.models.user import User, Role
from app.models.organization import Organization
from app.models.relationship import BusinessRelationship
from app.models.kpi import KPI, PerceptionScore, PerceptionGap, GapSeverity
from app.services.kpi_service import recalculate_gap, score_to_response, enrich_kpi_response


# ── SQLite UUID adapter ─────────────────────────────────────────────
# Register adapter so SQLite can bind uuid.UUID objects as strings.
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))


# ── Constants ───────────────────────────────────────────────────────

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_PERIOD = "2026-Q1"


# ── Database fixtures ───────────────────────────────────────────────

def _patch_columns_for_sqlite():
    """Swap PostgreSQL-specific column types for SQLite compatibility.

    Replaces JSONB with JSON and makes UUID columns use native_uuid=False
    so values are stored/retrieved as strings instead of native UUIDs.
    """
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            if isinstance(col.type, (PG_UUID, Uuid)):
                col.type = Uuid(native_uuid=False)


@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)

    # SQLite compatibility: disable FKs
    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    _patch_columns_for_sqlite()

    # Deduplicate indexes for SQLite
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = []
        for idx in table.indexes:
            if idx.name not in seen_idx:
                seen_idx.add(idx.name)
                deduped.append(idx)
        table.indexes.clear()
        table.indexes.update(deduped)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(engine):
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()


# ── Seed data ───────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def seed(db: AsyncSession):
    """Create minimal data for KPI workflow tests."""

    # Tenant
    tenant = Tenant(id=TENANT_ID, name="Test Tenant", slug="test-tenant", is_active=True)
    db.add(tenant)
    await db.flush()

    # User (for scored_by references)
    user = User(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        username="scorer_user", email="scorer@test.com",
        full_name="Scorer User", password_hash="x",
        role=Role.ADMIN, is_active=True,
    )
    db.add(user)
    await db.flush()

    # Organizations
    org_internal = Organization(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        name="Our Company", code="OUR", org_type="internal", is_active=True,
    )
    org_external = Organization(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        name="Partner Corp", code="PTR", org_type="vendor", is_active=True,
    )
    db.add_all([org_internal, org_external])
    await db.flush()

    # Business Relationship
    relationship = BusinessRelationship(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        org_a_id=org_internal.id, org_b_id=org_external.id,
        relationship_type="customer", status="active",
        name="Test Relationship",
    )
    db.add(relationship)
    await db.flush()

    # KPI
    kpi = KPI(
        id=uuid.uuid4(), relationship_id=relationship.id,
        name="Service Quality", category="quality",
        is_active=True,
    )
    db.add(kpi)
    await db.commit()

    return {
        "tenant": tenant,
        "user": user,
        "org_internal": org_internal,
        "org_external": org_external,
        "relationship": relationship,
        "kpi": kpi,
    }


# ── Helper ──────────────────────────────────────────────────────────

def _make_score(
    kpi_id: uuid.UUID,
    scorer_org_id: uuid.UUID,
    score: float,
    is_internal: bool,
    approval_status: str = "approved",
    scored_by_user_id: uuid.UUID | None = None,
    period: str = TEST_PERIOD,
) -> PerceptionScore:
    """Create a PerceptionScore instance."""
    return PerceptionScore(
        id=uuid.uuid4(),
        kpi_id=kpi_id,
        scorer_org_id=scorer_org_id,
        scored_by_user_id=scored_by_user_id,
        score=Decimal(str(score)),
        period=period,
        is_internal=is_internal,
        approval_status=approval_status,
        scored_at=datetime.utcnow(),
    )


# ── Tests ───────────────────────────────────────────────────────────

class TestRecalculateGap:
    """Tests for recalculate_gap() service function."""

    @pytest.mark.asyncio
    async def test_recalculate_gap_with_approved_scores(self, db, seed):
        """Create approved internal and external scores, verify gap computation."""
        kpi = seed["kpi"]
        org_int = seed["org_internal"]
        org_ext = seed["org_external"]

        # Internal scores: 8.0 and 9.0 → avg = 8.5
        db.add(_make_score(kpi.id, org_int.id, 8.0, is_internal=True))
        db.add(_make_score(kpi.id, org_int.id, 9.0, is_internal=True))
        # External scores: 6.0 and 7.0 → avg = 6.5
        db.add(_make_score(kpi.id, org_ext.id, 6.0, is_internal=False))
        db.add(_make_score(kpi.id, org_ext.id, 7.0, is_internal=False))
        await db.commit()

        await recalculate_gap(kpi.id, TEST_PERIOD, db)

        # Fetch the gap record
        result = await db.execute(
            select(PerceptionGap).where(
                PerceptionGap.kpi_id == kpi.id,
                PerceptionGap.period == TEST_PERIOD,
            )
        )
        gap = result.scalar_one()

        assert gap.internal_score == Decimal("8.50")
        assert gap.external_score == Decimal("6.50")
        assert gap.gap == Decimal("2.00")  # 8.5 - 6.5
        assert gap.gap_severity == "significant"  # 2.0 → significant (2-3 range)
        assert gap.requires_action is True

    @pytest.mark.asyncio
    async def test_recalculate_gap_excludes_rejected_scores(self, db, seed):
        """Rejected scores should not be included in gap calculation."""
        kpi = seed["kpi"]
        org_int = seed["org_internal"]
        org_ext = seed["org_external"]

        # Approved internal: 8.0
        db.add(_make_score(kpi.id, org_int.id, 8.0, is_internal=True, approval_status="approved"))
        # Rejected internal: 2.0 (should be excluded)
        db.add(_make_score(kpi.id, org_int.id, 2.0, is_internal=True, approval_status="rejected"))
        # Approved external: 7.0
        db.add(_make_score(kpi.id, org_ext.id, 7.0, is_internal=False, approval_status="approved"))
        # Draft external: 1.0 (should be excluded)
        db.add(_make_score(kpi.id, org_ext.id, 1.0, is_internal=False, approval_status="draft"))
        await db.commit()

        await recalculate_gap(kpi.id, TEST_PERIOD, db)

        result = await db.execute(
            select(PerceptionGap).where(
                PerceptionGap.kpi_id == kpi.id,
                PerceptionGap.period == TEST_PERIOD,
            )
        )
        gap = result.scalar_one()

        # Only approved scores: internal=8.0, external=7.0
        assert gap.internal_score == Decimal("8.00")
        assert gap.external_score == Decimal("7.00")
        assert gap.gap == Decimal("1.00")
        assert gap.gap_severity == "moderate"  # 1.0 → moderate (1-2 range)
        assert gap.requires_action is False

    @pytest.mark.asyncio
    async def test_recalculate_gap_minor_severity(self, db, seed):
        """Gap < 1 should be classified as minor."""
        kpi = seed["kpi"]
        org_int = seed["org_internal"]
        org_ext = seed["org_external"]

        db.add(_make_score(kpi.id, org_int.id, 7.5, is_internal=True))
        db.add(_make_score(kpi.id, org_ext.id, 7.0, is_internal=False))
        await db.commit()

        await recalculate_gap(kpi.id, TEST_PERIOD, db)

        result = await db.execute(
            select(PerceptionGap).where(
                PerceptionGap.kpi_id == kpi.id,
                PerceptionGap.period == TEST_PERIOD,
            )
        )
        gap = result.scalar_one()

        assert gap.gap == Decimal("0.50")
        assert gap.gap_severity == "minor"
        assert gap.requires_action is False

    @pytest.mark.asyncio
    async def test_recalculate_gap_critical_severity(self, db, seed):
        """Gap >= 3 should be classified as critical and require action."""
        kpi = seed["kpi"]
        org_int = seed["org_internal"]
        org_ext = seed["org_external"]

        db.add(_make_score(kpi.id, org_int.id, 9.0, is_internal=True))
        db.add(_make_score(kpi.id, org_ext.id, 5.0, is_internal=False))
        await db.commit()

        await recalculate_gap(kpi.id, TEST_PERIOD, db)

        result = await db.execute(
            select(PerceptionGap).where(
                PerceptionGap.kpi_id == kpi.id,
                PerceptionGap.period == TEST_PERIOD,
            )
        )
        gap = result.scalar_one()

        assert gap.gap == Decimal("4.00")
        assert gap.gap_severity == "critical"
        assert gap.requires_action is True


class TestScoreToResponse:
    """Tests for score_to_response() mapping function."""

    @pytest.mark.asyncio
    async def test_score_to_response_mapping(self, db, seed):
        """Verify score_to_response correctly maps model fields to response."""
        kpi = seed["kpi"]
        org = seed["org_internal"]
        user = seed["user"]

        score = PerceptionScore(
            id=uuid.uuid4(),
            kpi_id=kpi.id,
            scorer_org_id=org.id,
            scored_by_user_id=user.id,
            score=Decimal("8.50"),
            period=TEST_PERIOD,
            comments="Good performance",
            is_internal=True,
            approval_status="approved",
            scored_at=datetime.utcnow(),
        )
        db.add(score)
        await db.commit()

        # Reload with relationships
        result = await db.execute(
            select(PerceptionScore).where(PerceptionScore.id == score.id)
        )
        loaded_score = result.scalar_one()

        # Eagerly load the relationships for score_to_response
        # The function accesses score.scorer_org, score.scored_by, score.approver
        await db.refresh(loaded_score, ["scorer_org", "scored_by", "approver"])

        response = score_to_response(loaded_score)

        assert response.id == score.id
        assert response.kpi_id == kpi.id
        assert response.scorer_org_id == org.id
        assert response.scored_by_user_id == user.id
        assert response.score == Decimal("8.50")
        assert response.period == TEST_PERIOD
        assert response.comments == "Good performance"
        assert response.is_internal is True
        assert response.approval_status == "approved"
        assert response.scorer_org_name == "Our Company"
        assert response.scored_by_name == "Scorer User"
        assert response.approver_name is None  # No approver set


class TestEnrichKPIResponse:
    """Tests for enrich_kpi_response() service function."""

    @pytest.mark.asyncio
    async def test_enrich_kpi_response_with_gap(self, db, seed):
        """Verify enrich_kpi_response adds latest gap data to the response."""
        kpi = seed["kpi"]

        # Create a PerceptionGap record
        gap = PerceptionGap(
            id=uuid.uuid4(),
            kpi_id=kpi.id,
            period=TEST_PERIOD,
            internal_score=Decimal("8.00"),
            external_score=Decimal("6.00"),
            gap=Decimal("2.00"),
            gap_severity="significant",
            requires_action=True,
            calculated_at=datetime.utcnow(),
        )
        db.add(gap)
        await db.commit()

        # Reload the KPI
        result = await db.execute(select(KPI).where(KPI.id == kpi.id))
        loaded_kpi = result.scalar_one()

        response = await enrich_kpi_response(loaded_kpi, db)

        assert response.id == kpi.id
        assert response.name == "Service Quality"
        assert response.latest_internal_score == Decimal("8.00")
        assert response.latest_external_score == Decimal("6.00")
        assert response.latest_gap == Decimal("2.00")
        assert response.latest_gap_severity == "significant"

    @pytest.mark.asyncio
    async def test_enrich_kpi_response_without_gap(self, db, seed):
        """Verify enrich_kpi_response handles KPI with no gap data."""
        kpi = seed["kpi"]

        result = await db.execute(select(KPI).where(KPI.id == kpi.id))
        loaded_kpi = result.scalar_one()

        response = await enrich_kpi_response(loaded_kpi, db)

        assert response.id == kpi.id
        assert response.name == "Service Quality"
        assert response.latest_internal_score is None
        assert response.latest_external_score is None
        assert response.latest_gap is None
        assert response.latest_gap_severity is None

    @pytest.mark.asyncio
    async def test_enrich_kpi_response_uses_latest_period(self, db, seed):
        """When multiple gaps exist, enrich should use the most recent period."""
        kpi = seed["kpi"]

        # Older gap
        gap_old = PerceptionGap(
            id=uuid.uuid4(),
            kpi_id=kpi.id,
            period="2025-Q4",
            internal_score=Decimal("7.00"),
            external_score=Decimal("5.00"),
            gap=Decimal("2.00"),
            gap_severity="significant",
            requires_action=True,
            calculated_at=datetime.utcnow(),
        )
        # Newer gap
        gap_new = PerceptionGap(
            id=uuid.uuid4(),
            kpi_id=kpi.id,
            period="2026-Q1",
            internal_score=Decimal("9.00"),
            external_score=Decimal("8.50"),
            gap=Decimal("0.50"),
            gap_severity="minor",
            requires_action=False,
            calculated_at=datetime.utcnow(),
        )
        db.add_all([gap_old, gap_new])
        await db.commit()

        result = await db.execute(select(KPI).where(KPI.id == kpi.id))
        loaded_kpi = result.scalar_one()

        response = await enrich_kpi_response(loaded_kpi, db)

        # Should use 2026-Q1 (latest period by desc sort)
        assert response.latest_internal_score == Decimal("9.00")
        assert response.latest_external_score == Decimal("8.50")
        assert response.latest_gap == Decimal("0.50")
        assert response.latest_gap_severity == "minor"
