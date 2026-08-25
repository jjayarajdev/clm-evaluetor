"""Regression test for the provider/client obligation split in the contract
intelligence endpoint.

The old split matched English keywords only ("provider"/"vendor"), so every
obligation of a French contract (parties like OPENWORK / SQUARE ONE) landed
on the client side. The split now matches the obligated party against the
contract's counterparty name (language-neutral), keeping the keyword
fallback for legacy rows.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.deps import get_current_user, get_current_tenant_id
from app.database import Base, get_db
from app.main import app
from app.models.contract import Contract, ContractStatus
from app.models.obligation import Obligation
from app.models.tenant import Tenant
from app.models.user import Role, User

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = [i for i in table.indexes if i.name not in seen_idx and not seen_idx.add(i.name)]
        table.indexes.clear()
        table.indexes.update(deduped)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _client(db) -> AsyncClient:
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


def _obligation(contract_id, party: str, desc: str) -> Obligation:
    return Obligation(
        id=uuid.uuid4(), contract_id=contract_id,
        description=desc, obligated_party=party,
    )


@pytest.mark.asyncio
async def test_counterparty_obligations_are_provider_side(db):
    db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
    contract = Contract(
        id=uuid.uuid4(), tenant_id=TENANT_ID, filename="Contrat SQ1-OW.pdf",
        file_path="/u/c.pdf", status=ContractStatus.COMPLETED,
        uploaded_by=USER_ID, version=1, counterparty="OPENWORK",
    )
    db.add(contract)
    db.add_all([
        _obligation(contract.id, "OPENWORK", "Transmettre le rapport mensuel"),
        _obligation(contract.id, "SQUARE ONE", "Paiement à 45 jours"),
        _obligation(contract.id, "Provider", "Legacy english-labelled row"),
    ])
    await db.commit()

    async with _client(db) as client:
        resp = await client.get(f"/api/dashboard/intelligence/{contract.id}")
    assert resp.status_code == 200, resp.text
    matrix = resp.json()["obligations_matrix"]
    provider_parties = {o["obligated_party"] for o in matrix["provider_obligations"]}
    client_parties = {o["obligated_party"] for o in matrix["client_obligations"]}
    # Counterparty-name match (language-neutral) + legacy keyword fallback.
    assert provider_parties == {"OPENWORK", "Provider"}
    assert client_parties == {"SQUARE ONE"}
    assert matrix["total_count"] == 3
