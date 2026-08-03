"""Tests for organization and relationship deletion.

Rules under test:
- Organization delete defaults to deactivation; hard delete is blocked (409)
  while relationships, contracts, or subsidiaries reference the org.
- Relationship delete cascades all governance data (KPIs + scores/gaps,
  surveys + responses, improvements + actions, team, history, service links)
  but only DETACHES contracts and external tokens, and never touches orgs.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import JSON, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.contract import Contract, ContractStatus
from app.models.external_access import ExternalAccessToken
from app.models.improvement import ImprovementAction, ImprovementPoint
from app.models.kpi import KPI, PerceptionGap, PerceptionScore
from app.models.organization import Organization
from app.models.organization_officer import OrganizationOfficer
from app.models.relationship import BusinessRelationship, RelationshipTeam
from app.models.relationship_history import RelationshipStatusHistory
from app.models.service_portfolio import RelationshipService, ServicePortfolio
from app.models.survey import SurveyInstance, SurveyQuestion, SurveyResponse, SurveyTemplate
from app.models.tenant import Tenant
from app.models.user import Role, User

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest_asyncio.fixture(scope="function")
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = [i for i in table.indexes if i.name not in seen_idx and not seen_idx.add(i.name)]
        table.indexes.clear()
        table.indexes.update(deduped)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(eng, expire_on_commit=False)
    async with maker() as session:
        yield session
    await eng.dispose()


def _org(name: str) -> Organization:
    return Organization(
        id=uuid.uuid4(), tenant_id=TENANT_ID, name=name, code=name.upper()[:10],
        is_active=True,
    )


def _rel(org_a: Organization, org_b: Organization) -> BusinessRelationship:
    return BusinessRelationship(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        org_a_id=org_a.id, org_b_id=org_b.id,
        relationship_type="supplier", status="active",
    )


def _base(db):
    db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
    db.add(User(
        id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
        full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
    ))


def _client(db):
    async def override_db():
        yield db

    user = User(
        id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
        full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_ID
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


async def _count(db, model) -> int:
    return len((await db.execute(select(model))).scalars().all())


class TestOrganizationDelete:
    @pytest.mark.asyncio
    async def test_default_delete_deactivates(self, db):
        _base(db)
        org = _org("Acme")
        db.add(org)
        await db.commit()

        async with _client(db) as c:
            r = await c.delete(f"/api/organizations/{org.id}")
        assert r.status_code == 204
        assert org.is_active is False
        assert await _count(db, Organization) == 1  # still there

    @pytest.mark.asyncio
    async def test_hard_delete_blocked_by_references(self, db):
        _base(db)
        org, other, child = _org("Acme"), _org("Other"), _org("Child")
        child.parent_organization_id = org.id
        db.add_all([org, other, child])
        db.add(_rel(org, other))
        db.add(Contract(
            id=uuid.uuid4(), tenant_id=TENANT_ID, filename="c.pdf", file_path="/tmp/c.pdf",
            status=ContractStatus.COMPLETED, uploaded_by=USER_ID, organization_id=org.id,
        ))
        await db.commit()

        async with _client(db) as c:
            r = await c.delete(f"/api/organizations/{org.id}?hard_delete=true")
        assert r.status_code == 409
        detail = r.json()["detail"]
        assert "1 business relationship(s)" in detail
        assert "1 contract(s)" in detail
        assert "1 subsidiary organization(s)" in detail
        assert await _count(db, Organization) == 3  # nothing deleted

    @pytest.mark.asyncio
    async def test_hard_delete_clean_org_removes_officers(self, db):
        _base(db)
        org = _org("Acme")
        db.add(org)
        db.add(OrganizationOfficer(
            id=uuid.uuid4(), tenant_id=TENANT_ID, organization_id=org.id,
            name="Jane Doe", governance_role="other",
        ))
        await db.commit()

        async with _client(db) as c:
            r = await c.delete(f"/api/organizations/{org.id}?hard_delete=true")
        assert r.status_code == 204
        assert await _count(db, Organization) == 0
        assert await _count(db, OrganizationOfficer) == 0


class TestRelationshipDelete:
    @pytest_asyncio.fixture
    async def seeded(self, db):
        _base(db)
        org_a, org_b = _org("Us"), _org("Vendor")
        rel = _rel(org_a, org_b)
        other_rel = _rel(org_a, org_b)
        db.add_all([org_a, org_b, rel, other_rel])

        kpi = KPI(id=uuid.uuid4(), relationship_id=rel.id,
                  name="Quality", category="quality")
        db.add(kpi)
        db.add(PerceptionScore(
            id=uuid.uuid4(), kpi_id=kpi.id, score=4, period="2026-Q2",
            scorer_org_id=org_a.id, scored_by_user_id=USER_ID,
            scored_at=datetime.now(timezone.utc),
        ))
        db.add(PerceptionGap(
            id=uuid.uuid4(), kpi_id=kpi.id, period="2026-Q2",
            gap=1.5, calculated_at=datetime.now(timezone.utc),
        ))

        template = SurveyTemplate(id=uuid.uuid4(), tenant_id=TENANT_ID, name="Perception survey")
        db.add(template)
        question = SurveyQuestion(
            id=uuid.uuid4(), template_id=template.id, text="Rate quality",
            sequence=1, kpi_id=kpi.id,
        )
        db.add(question)
        instance = SurveyInstance(
            id=uuid.uuid4(), template_id=template.id,
            relationship_id=rel.id, period="2026-Q2",
        )
        db.add(instance)
        db.add(SurveyResponse(
            id=uuid.uuid4(), survey_instance_id=instance.id, answers={"q": 4},
        ))

        point = ImprovementPoint(
            id=uuid.uuid4(), relationship_id=rel.id,
            kpi_id=kpi.id, title="Improve response times",
        )
        db.add(point)
        db.add(ImprovementAction(
            id=uuid.uuid4(), improvement_id=point.id, description="Add SLA dashboard",
        ))

        db.add(RelationshipTeam(
            id=uuid.uuid4(), relationship_id=rel.id,
            user_id=USER_ID, role="relationship_manager",
        ))
        db.add(RelationshipStatusHistory(
            id=uuid.uuid4(), tenant_id=TENANT_ID, relationship_id=rel.id,
            status="good", period="2026-Q2",
            recorded_date=datetime.now(timezone.utc),
        ))

        portfolio = ServicePortfolio(
            id=uuid.uuid4(), tenant_id=TENANT_ID, organization_id=org_b.id,
            name="IT Services", code="ITS",
        )
        db.add(portfolio)
        db.add(RelationshipService(
            id=uuid.uuid4(), relationship_id=rel.id,
            service_portfolio_id=portfolio.id,
        ))

        contract = Contract(
            id=uuid.uuid4(), tenant_id=TENANT_ID, filename="c.pdf", file_path="/tmp/c.pdf",
            status=ContractStatus.COMPLETED, uploaded_by=USER_ID,
            business_relationship_id=rel.id, organization_id=org_b.id,
        )
        db.add(contract)
        db.add(ExternalAccessToken(
            id=uuid.uuid4(), relationship_id=rel.id,
            token="tok-12345678", token_type="survey_response",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            created_by_id=USER_ID,
        ))
        await db.commit()
        return {"rel": rel, "other_rel": other_rel, "kpi": kpi, "question": question,
                "contract": contract, "org_a": org_a, "org_b": org_b}

    @pytest.mark.asyncio
    async def test_delete_cascades_governance_data(self, db, seeded):
        async with _client(db) as c:
            r = await c.delete(f"/api/relationships/{seeded['rel'].id}")
        assert r.status_code == 204

        for model in (KPI, PerceptionScore, PerceptionGap, SurveyInstance,
                      SurveyResponse, ImprovementPoint, ImprovementAction,
                      RelationshipTeam, RelationshipStatusHistory, RelationshipService):
            assert await _count(db, model) == 0, model.__name__

        # The other relationship survives
        rels = (await db.execute(select(BusinessRelationship))).scalars().all()
        assert [r_.id for r_ in rels] == [seeded["other_rel"].id]

    @pytest.mark.asyncio
    async def test_delete_detaches_but_keeps_contract_and_token(self, db, seeded):
        async with _client(db) as c:
            await c.delete(f"/api/relationships/{seeded['rel'].id}")

        contract = (await db.execute(select(Contract))).scalars().one()
        assert contract.business_relationship_id is None
        assert contract.organization_id == seeded["org_b"].id  # org link untouched

        token = (await db.execute(select(ExternalAccessToken))).scalars().one()
        assert token.relationship_id is None

        # Orgs and survey template/question survive; question is detached from the KPI
        assert await _count(db, Organization) == 2
        question = (await db.execute(select(SurveyQuestion))).scalars().one()
        assert question.kpi_id is None

    @pytest.mark.asyncio
    async def test_delete_requires_admin(self, db, seeded):
        async def override_db():
            yield db

        legal = User(
            id=uuid.uuid4(), tenant_id=TENANT_ID, username="l", email="l@t.com",
            full_name="L", password_hash="x", role=Role.LEGAL, is_active=True,
        )
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: legal
        app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_ID
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(f"/api/relationships/{seeded['rel'].id}")
        assert r.status_code == 403
        assert await _count(db, KPI) == 1  # nothing deleted
