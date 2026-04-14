"""Business Unit scoping tests.

Verifies that apply_bu_filter() correctly restricts contract visibility
based on user role and business unit assignment.
"""

import pytest
import pytest_asyncio
import sqlite3
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import event, select, JSON, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.core.tenant import apply_bu_filter
from app.models.tenant import Tenant
from app.models.user import User, Role
from app.models.contract import Contract, ContractStatus, ContractType
from app.models.business_unit import BusinessUnit


# ── SQLite UUID adapter ─────────────────────────────────────────────
# Register adapter so SQLite can bind uuid.UUID objects as strings.
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))


# ── Constants ───────────────────────────────────────────────────────

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BU_ALPHA_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
BU_BETA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


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
    """Create tenant, BUs, users, and contracts for BU scoping tests."""

    # Tenant
    tenant = Tenant(id=TENANT_ID, name="Test Tenant", slug="test-tenant", is_active=True)
    db.add(tenant)
    await db.flush()

    # Business Units
    bu_alpha = BusinessUnit(
        id=BU_ALPHA_ID, tenant_id=TENANT_ID,
        name="Alpha Division", code="ALPHA", is_active=True,
    )
    bu_beta = BusinessUnit(
        id=BU_BETA_ID, tenant_id=TENANT_ID,
        name="Beta Division", code="BETA", is_active=True,
    )
    db.add_all([bu_alpha, bu_beta])
    await db.flush()

    # Users
    admin_user = User(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        username="admin_user", email="admin@test.com",
        full_name="Admin User", password_hash="x",
        role=Role.ADMIN, is_active=True,
        business_unit_id=None,  # admin without BU
    )
    legal_alpha = User(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        username="legal_alpha", email="legal_alpha@test.com",
        full_name="Legal Alpha", password_hash="x",
        role=Role.LEGAL, is_active=True,
        business_unit_id=BU_ALPHA_ID,
    )
    legal_beta = User(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        username="legal_beta", email="legal_beta@test.com",
        full_name="Legal Beta", password_hash="x",
        role=Role.LEGAL, is_active=True,
        business_unit_id=BU_BETA_ID,
    )
    super_admin = User(
        id=uuid.uuid4(), tenant_id=None,
        username="superadmin", email="super@test.com",
        full_name="Super Admin", password_hash="x",
        role=Role.SUPER_ADMIN, is_active=True,
        business_unit_id=None,
    )
    db.add_all([admin_user, legal_alpha, legal_beta, super_admin])
    await db.flush()

    # Contracts: 2 with BU, 1 unassigned
    contract_alpha = Contract(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        filename="alpha.pdf", file_path="/alpha.pdf", file_size=100,
        status=ContractStatus.COMPLETED, counterparty="Vendor Alpha",
        contract_type=ContractType.MSA,
        effective_date=date.today(),
        expiration_date=date.today() + timedelta(days=365),
        contract_value=50000, currency="USD",
        uploaded_by=admin_user.id,
        business_unit_id=BU_ALPHA_ID,
    )
    contract_beta = Contract(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        filename="beta.pdf", file_path="/beta.pdf", file_size=200,
        status=ContractStatus.COMPLETED, counterparty="Vendor Beta",
        contract_type=ContractType.SOW,
        effective_date=date.today(),
        expiration_date=date.today() + timedelta(days=180),
        contract_value=30000, currency="USD",
        uploaded_by=admin_user.id,
        business_unit_id=BU_BETA_ID,
    )
    contract_unassigned = Contract(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        filename="unassigned.pdf", file_path="/unassigned.pdf", file_size=150,
        status=ContractStatus.COMPLETED, counterparty="Vendor Unassigned",
        contract_type=ContractType.NDA,
        effective_date=date.today(),
        expiration_date=date.today() + timedelta(days=90),
        contract_value=10000, currency="USD",
        uploaded_by=admin_user.id,
        business_unit_id=None,
    )
    db.add_all([contract_alpha, contract_beta, contract_unassigned])
    await db.commit()

    return {
        "admin_user": admin_user,
        "legal_alpha": legal_alpha,
        "legal_beta": legal_beta,
        "super_admin": super_admin,
        "contract_alpha": contract_alpha,
        "contract_beta": contract_beta,
        "contract_unassigned": contract_unassigned,
    }


# ── Tests ───────────────────────────────────────────────────────────

class TestBUScoping:
    """Tests for apply_bu_filter() business unit access control."""

    @pytest.mark.asyncio
    async def test_admin_without_bu_sees_all_contracts(self, db, seed):
        """Admin user (no BU assigned) should see all 3 contracts in the tenant."""
        user = seed["admin_user"]

        query = select(Contract).where(Contract.tenant_id == TENANT_ID)
        query = apply_bu_filter(query, user.business_unit_id, user.role.value)

        result = await db.execute(query)
        contracts = result.scalars().all()

        assert len(contracts) == 3
        filenames = {c.filename for c in contracts}
        assert filenames == {"alpha.pdf", "beta.pdf", "unassigned.pdf"}

    @pytest.mark.asyncio
    async def test_bu_scoped_user_sees_own_bu_and_unassigned(self, db, seed):
        """Legal user in Alpha BU should see Alpha contracts + unassigned, not Beta."""
        user = seed["legal_alpha"]

        query = select(Contract).where(Contract.tenant_id == TENANT_ID)
        query = apply_bu_filter(query, user.business_unit_id, user.role.value)

        result = await db.execute(query)
        contracts = result.scalars().all()

        assert len(contracts) == 2
        filenames = {c.filename for c in contracts}
        assert "alpha.pdf" in filenames
        assert "unassigned.pdf" in filenames
        assert "beta.pdf" not in filenames

    @pytest.mark.asyncio
    async def test_bu_scoped_user_beta_sees_own_bu_and_unassigned(self, db, seed):
        """Legal user in Beta BU should see Beta contracts + unassigned, not Alpha."""
        user = seed["legal_beta"]

        query = select(Contract).where(Contract.tenant_id == TENANT_ID)
        query = apply_bu_filter(query, user.business_unit_id, user.role.value)

        result = await db.execute(query)
        contracts = result.scalars().all()

        assert len(contracts) == 2
        filenames = {c.filename for c in contracts}
        assert "beta.pdf" in filenames
        assert "unassigned.pdf" in filenames
        assert "alpha.pdf" not in filenames

    @pytest.mark.asyncio
    async def test_super_admin_sees_everything(self, db, seed):
        """Super admin (tenant_id=None, no BU) should bypass BU filtering."""
        user = seed["super_admin"]

        # Super admin: no tenant filter, no BU filter
        query = select(Contract)
        query = apply_bu_filter(query, user.business_unit_id, user.role.value)

        result = await db.execute(query)
        contracts = result.scalars().all()

        assert len(contracts) == 3
        filenames = {c.filename for c in contracts}
        assert filenames == {"alpha.pdf", "beta.pdf", "unassigned.pdf"}

    @pytest.mark.asyncio
    async def test_user_without_bu_assignment_sees_all(self, db, seed):
        """Non-admin user with no BU assigned sees all contracts (legacy behavior)."""
        # apply_bu_filter returns unfiltered query when business_unit_id is None
        # regardless of role (first check in the function)
        query = select(Contract).where(Contract.tenant_id == TENANT_ID)
        query = apply_bu_filter(query, None, "legal")

        result = await db.execute(query)
        contracts = result.scalars().all()

        assert len(contracts) == 3

    @pytest.mark.asyncio
    async def test_admin_with_bu_still_sees_all(self, db, seed):
        """Admin user even WITH a BU assigned should still see all contracts."""
        # Admin role bypasses BU filter regardless of BU assignment
        query = select(Contract).where(Contract.tenant_id == TENANT_ID)
        query = apply_bu_filter(query, BU_ALPHA_ID, "admin")

        result = await db.execute(query)
        contracts = result.scalars().all()

        assert len(contracts) == 3
        filenames = {c.filename for c in contracts}
        assert filenames == {"alpha.pdf", "beta.pdf", "unassigned.pdf"}
