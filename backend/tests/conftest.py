"""Pytest configuration and fixtures for CLM tests."""

import pytest
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.user import User, Role
from app.models.tenant import Tenant
from app.models.contract import Contract, ContractStatus, ContractType, RiskLevel
from app.models.business_unit import BusinessUnit
from app.models.external_user import ExternalUser
from app.models.clause import Clause, ClauseType
from app.models.obligation import Obligation, ObligationStatus


# Test database URL (in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Database fixtures
@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session, test_user, test_tenant) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with mocked dependencies."""

    async def override_get_db():
        yield db_session

    def override_get_current_user():
        return test_user

    def override_get_current_tenant_id():
        return test_tenant.id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_tenant_id] = override_get_current_tenant_id

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ID fixtures
@pytest.fixture
def tenant_id() -> uuid.UUID:
    """Generate a test tenant ID."""
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    """Generate a test user ID."""
    return uuid.uuid4()


@pytest.fixture
def contract_id() -> uuid.UUID:
    """Generate a test contract ID."""
    return uuid.uuid4()


@pytest.fixture
def business_unit_id() -> uuid.UUID:
    """Generate a test business unit ID."""
    return uuid.uuid4()


@pytest.fixture
def external_user_id() -> uuid.UUID:
    """Generate a test external user ID."""
    return uuid.uuid4()


# Model fixtures
@pytest.fixture
def test_tenant(tenant_id) -> Tenant:
    """Create a test tenant."""
    return Tenant(
        id=tenant_id,
        name="Test Tenant",
        slug="test-tenant",
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_user(user_id, tenant_id) -> User:
    """Create a test user."""
    return User(
        id=user_id,
        tenant_id=tenant_id,
        email="testuser@example.com",
        full_name="Test User",
        hashed_password="hashed_password_here",
        role=Role.ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_legal_user(tenant_id) -> User:
    """Create a test legal user."""
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="legal@example.com",
        full_name="Legal User",
        hashed_password="hashed_password_here",
        role=Role.LEGAL,
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_procurement_user(tenant_id) -> User:
    """Create a test procurement user."""
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="procurement@example.com",
        full_name="Procurement User",
        hashed_password="hashed_password_here",
        role=Role.PROCUREMENT,
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_viewer_user(tenant_id) -> User:
    """Create a test viewer user."""
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="viewer@example.com",
        full_name="Viewer User",
        hashed_password="hashed_password_here",
        role=Role.VIEWER,
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_super_admin() -> User:
    """Create a test super admin user."""
    return User(
        id=uuid.uuid4(),
        tenant_id=None,
        email="superadmin@example.com",
        full_name="Super Admin",
        hashed_password="hashed_password_here",
        role=Role.SUPER_ADMIN,
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_business_unit(business_unit_id, tenant_id) -> BusinessUnit:
    """Create a test business unit."""
    return BusinessUnit(
        id=business_unit_id,
        tenant_id=tenant_id,
        name="Test Business Unit",
        code="TBU",
        description="Test business unit description",
        is_active=True,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_contract(contract_id, tenant_id) -> Contract:
    """Create a test contract."""
    return Contract(
        id=contract_id,
        tenant_id=tenant_id,
        filename="test_contract.pdf",
        original_filename="Test Contract.pdf",
        file_path="/uploads/test_contract.pdf",
        file_size=1024,
        mime_type="application/pdf",
        contract_type=ContractType.MASTER_SERVICE_AGREEMENT,
        status=ContractStatus.COMPLETED,
        counterparty="Test Counterparty",
        effective_date=datetime.utcnow().date(),
        expiration_date=(datetime.utcnow() + timedelta(days=365)).date(),
        total_value=100000.00,
        currency="USD",
        risk_level=RiskLevel.MEDIUM,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def test_contract_with_details(test_contract) -> Contract:
    """Create a test contract with clauses and obligations."""
    test_contract.clauses = [
        Clause(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            clause_type=ClauseType.TERMINATION,
            title="Termination Clause",
            content="Either party may terminate with 30 days notice.",
            section_number="5.1",
            page_number=5,
            created_at=datetime.utcnow(),
        ),
        Clause(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            clause_type=ClauseType.CONFIDENTIALITY,
            title="Confidentiality Clause",
            content="All information shall be kept confidential.",
            section_number="6.1",
            page_number=6,
            created_at=datetime.utcnow(),
        ),
    ]
    test_contract.obligations = [
        Obligation(
            id=uuid.uuid4(),
            contract_id=test_contract.id,
            title="Quarterly Reporting",
            description="Submit quarterly performance reports.",
            due_date=(datetime.utcnow() + timedelta(days=90)).date(),
            status=ObligationStatus.PENDING,
            responsible_party="vendor",
            created_at=datetime.utcnow(),
        ),
    ]
    return test_contract


@pytest.fixture
def test_external_user(external_user_id, tenant_id) -> ExternalUser:
    """Create a test external user."""
    return ExternalUser(
        id=external_user_id,
        tenant_id=tenant_id,
        email="external@vendor.com",
        full_name="External Vendor",
        company_name="Vendor Corp",
        title="Contract Manager",
        phone="+1-555-0123",
        is_active=True,
        created_at=datetime.utcnow(),
    )


# Multiple contracts fixture
@pytest.fixture
def test_contracts(tenant_id) -> list[Contract]:
    """Create multiple test contracts."""
    contracts = []
    for i in range(5):
        contract = Contract(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            filename=f"contract_{i}.pdf",
            original_filename=f"Contract {i}.pdf",
            file_path=f"/uploads/contract_{i}.pdf",
            file_size=1024 * (i + 1),
            mime_type="application/pdf",
            contract_type=ContractType.MASTER_SERVICE_AGREEMENT,
            status=ContractStatus.COMPLETED,
            counterparty=f"Vendor {i}",
            effective_date=datetime.utcnow().date(),
            expiration_date=(datetime.utcnow() + timedelta(days=365)).date(),
            total_value=10000 * (i + 1),
            currency="USD",
            risk_level=[RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH][i % 3],
            created_at=datetime.utcnow(),
        )
        contracts.append(contract)
    return contracts


# Mock fixtures
@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="Mock AI response"))]
    ))
    return mock


@pytest.fixture
def mock_chromadb_client():
    """Create a mock ChromaDB client."""
    mock = MagicMock()
    mock.get_or_create_collection.return_value = MagicMock(
        add=MagicMock(),
        query=MagicMock(return_value={
            "documents": [["Sample document text"]],
            "metadatas": [[{"contract_id": "test-id"}]],
            "distances": [[0.1]],
        }),
    )
    return mock


@pytest.fixture
def mock_file_upload():
    """Create a mock file upload."""
    from io import BytesIO

    content = b"%PDF-1.4 sample pdf content"
    file = BytesIO(content)
    file.name = "test_upload.pdf"
    return file


# Authentication helpers
@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers for API requests."""
    return {"Authorization": f"Bearer test_token_{test_user.id}"}


@pytest.fixture
def super_admin_headers(test_super_admin):
    """Create super admin authentication headers."""
    return {
        "Authorization": f"Bearer test_token_{test_super_admin.id}",
        "X-Tenant-ID": str(uuid.uuid4()),
    }


# Utility functions
def create_test_contract(
    tenant_id: uuid.UUID,
    status: ContractStatus = ContractStatus.COMPLETED,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    **kwargs
) -> Contract:
    """Factory function to create test contracts with custom attributes."""
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "filename": "test_contract.pdf",
        "original_filename": "Test Contract.pdf",
        "file_path": "/uploads/test_contract.pdf",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "contract_type": ContractType.MASTER_SERVICE_AGREEMENT,
        "status": status,
        "counterparty": "Test Counterparty",
        "effective_date": datetime.utcnow().date(),
        "expiration_date": (datetime.utcnow() + timedelta(days=365)).date(),
        "total_value": 100000.00,
        "currency": "USD",
        "risk_level": risk_level,
        "created_at": datetime.utcnow(),
    }
    defaults.update(kwargs)
    return Contract(**defaults)


def create_test_user(
    tenant_id: uuid.UUID,
    role: Role = Role.LEGAL,
    **kwargs
) -> User:
    """Factory function to create test users with custom attributes."""
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "email": f"user_{uuid.uuid4().hex[:8]}@example.com",
        "full_name": "Test User",
        "hashed_password": "hashed_password",
        "role": role,
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    defaults.update(kwargs)
    return User(**defaults)
