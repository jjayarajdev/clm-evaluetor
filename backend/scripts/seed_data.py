#!/usr/bin/env python3
"""
Seed script to populate the database with multi-tenant demo data.
Run with: python -m scripts.seed_data
"""

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from sqlalchemy import text

from app.database import Base
from app.models import User, Contract, Clause
from app.models.tenant import Tenant
from app.models.clause import ClauseType
from app.models.contract import RiskLevel, ContractType, ContractStatus
from app.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


# Multi-tenant structure - each tenant gets a variety of contracts
TENANTS = [
    {
        "name": "Acme Corp",
        "slug": "acme",
        "contact_email": "admin@acme.com",
        "plan": "enterprise",
        "users": [
            {"username": "admin", "email": "admin@acme.com", "password": "admin123", "role": "admin"},
            {"username": "legal", "email": "legal@acme.com", "password": "legal123", "role": "legal"},
        ],
        "contracts": [
            {
                "filename": "MSA-TechServices-2024.pdf",
                "contract_type": "msa",
                "counterparty": "TechServices Inc",
                "contract_value": Decimal("500000.00"),
                "risk_level": "medium",
                "risk_score": 45,
                "status": "completed",
            },
            {
                "filename": "NDA-Strategic-Partner.pdf",
                "contract_type": "nda",
                "counterparty": "Strategic Partners LLC",
                "contract_value": None,
                "risk_level": "low",
                "risk_score": 15,
                "status": "completed",
            },
            {
                "filename": "Vendor-Agreement-GlobalSupply.pdf",
                "contract_type": "vendor_agreement",
                "counterparty": "GlobalSupply International",
                "contract_value": Decimal("1250000.00"),
                "risk_level": "high",
                "risk_score": 72,
                "status": "completed",
            },
            {
                "filename": "Amendment-to-MSA.pdf",
                "contract_type": "amendment",
                "counterparty": "TechServices Inc",
                "contract_value": Decimal("150000.00"),
                "risk_level": "critical",
                "risk_score": 85,
                "status": "completed",
            },
            {
                "filename": "Software-License-Enterprise.pdf",
                "contract_type": "license",
                "counterparty": "Enterprise Software Co",
                "contract_value": Decimal("320000.00"),
                "risk_level": "medium",
                "risk_score": 42,
                "status": "completed",
            },
        ],
    },
    {
        "name": "TechStart",
        "slug": "techstart",
        "contact_email": "admin@techstart.io",
        "plan": "professional",
        "users": [
            {"username": "techstart_admin", "email": "admin@techstart.io", "password": "admin123", "role": "admin"},
            {"username": "techstart_legal", "email": "legal@techstart.io", "password": "legal123", "role": "legal"},
        ],
        "contracts": [
            {
                "filename": "SaaS-Agreement-CloudProvider.pdf",
                "contract_type": "sow",
                "counterparty": "CloudProvider Inc",
                "contract_value": Decimal("75000.00"),
                "risk_level": "low",
                "risk_score": 22,
                "status": "completed",
            },
            {
                "filename": "Consulting-Agreement.pdf",
                "contract_type": "sow",
                "counterparty": "Expert Consultants",
                "contract_value": Decimal("50000.00"),
                "risk_level": "medium",
                "risk_score": 35,
                "status": "completed",
            },
            {
                "filename": "NDA-Investor-Relations.pdf",
                "contract_type": "nda",
                "counterparty": "Venture Capital Partners",
                "contract_value": None,
                "risk_level": "low",
                "risk_score": 12,
                "status": "completed",
            },
            {
                "filename": "MSA-DataCenter-Services.pdf",
                "contract_type": "msa",
                "counterparty": "DataCenter Solutions",
                "contract_value": Decimal("180000.00"),
                "risk_level": "medium",
                "risk_score": 38,
                "status": "completed",
            },
            {
                "filename": "Employment-CTO-Agreement.pdf",
                "contract_type": "employment_contract",
                "counterparty": "John Smith",
                "contract_value": Decimal("280000.00"),
                "risk_level": "low",
                "risk_score": 20,
                "status": "completed",
            },
        ],
    },
    {
        "name": "LegalCo",
        "slug": "legalco",
        "contact_email": "admin@legalco.com",
        "plan": "enterprise",
        "users": [
            {"username": "legalco_admin", "email": "admin@legalco.com", "password": "admin123", "role": "admin"},
            {"username": "legalco_legal", "email": "legal@legalco.com", "password": "legal123", "role": "legal"},
        ],
        "contracts": [
            {
                "filename": "Partnership-Agreement-JointVenture.pdf",
                "contract_type": "msa",
                "counterparty": "JointVenture Partners",
                "contract_value": Decimal("2000000.00"),
                "risk_level": "high",
                "risk_score": 68,
                "status": "completed",
            },
            {
                "filename": "Employment-Contract-Senior-Counsel.pdf",
                "contract_type": "employment_contract",
                "counterparty": "Jane Doe",
                "contract_value": Decimal("250000.00"),
                "risk_level": "low",
                "risk_score": 18,
                "status": "completed",
            },
            {
                "filename": "Vendor-Agreement-Office-Supplies.pdf",
                "contract_type": "vendor_agreement",
                "counterparty": "Office Supplies Corp",
                "contract_value": Decimal("45000.00"),
                "risk_level": "low",
                "risk_score": 10,
                "status": "completed",
            },
            {
                "filename": "NDA-Client-Confidential.pdf",
                "contract_type": "nda",
                "counterparty": "Major Bank Corp",
                "contract_value": None,
                "risk_level": "medium",
                "risk_score": 35,
                "status": "completed",
            },
            {
                "filename": "Service-Agreement-IT-Support.pdf",
                "contract_type": "sow",
                "counterparty": "IT Solutions Inc",
                "contract_value": Decimal("120000.00"),
                "risk_level": "medium",
                "risk_score": 40,
                "status": "completed",
            },
        ],
    },
]

# Super admin (system-level user)
SUPER_ADMIN = {
    "username": "superadmin",
    "email": "superadmin@system.local",
    "password": "admin123",
    "role": "super_admin",
}


def generate_sample_clauses(contract_id) -> list[dict]:
    """Generate sample clauses for a contract."""
    return [
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": ClauseType.LIMITATION_OF_LIABILITY,
            "text": "Neither party shall be liable for any indirect, incidental, special, consequential, or punitive damages.",
            "summary": "Limitation of Liability - excludes consequential damages",
            "risk_level": RiskLevel.HIGH,
            "risk_reason": "Broad limitation excludes consequential damages",
            "page_number": 8,
            "section_number": "12.1",
            "confidence_score": 0.92,
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": ClauseType.INDEMNIFICATION,
            "text": "Customer shall indemnify and hold harmless Provider from any claims arising from Customer's use of the Services.",
            "summary": "Indemnification - customer obligation",
            "risk_level": RiskLevel.MEDIUM,
            "risk_reason": "One-sided indemnification",
            "page_number": 9,
            "section_number": "13.1",
            "confidence_score": 0.88,
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": ClauseType.TERMINATION,
            "text": "Either party may terminate this Agreement upon 30 days written notice.",
            "summary": "Termination for convenience",
            "risk_level": RiskLevel.LOW,
            "page_number": 11,
            "section_number": "15.2",
            "confidence_score": 0.95,
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": ClauseType.CONFIDENTIALITY,
            "text": "Each party agrees to maintain confidentiality for 5 years following disclosure.",
            "summary": "Mutual confidentiality for 5 years",
            "risk_level": RiskLevel.LOW,
            "page_number": 6,
            "section_number": "8.1",
            "confidence_score": 0.91,
        },
    ]


async def seed_database():
    """Seed the database with multi-tenant demo data."""
    print("Starting multi-tenant database seeding...")

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        today = date.today()
        all_users = []

        # Create tenants with their users and contracts
        for tenant_data in TENANTS:
            print(f"\n{'='*50}")
            print(f"Creating tenant: {tenant_data['name']}")
            print('='*50)

            # Create tenant
            tenant = Tenant(
                id=uuid4(),
                name=tenant_data["name"],
                slug=tenant_data["slug"],
                contact_email=tenant_data["contact_email"],
                plan=tenant_data["plan"],
                is_active=True,
            )
            session.add(tenant)
            await session.flush()
            print(f"  ✓ Tenant: {tenant.name} ({tenant.slug})")

            # Create users for this tenant
            tenant_admin = None
            for user_data in tenant_data["users"]:
                user = User(
                    id=uuid4(),
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=hash_password(user_data["password"]),
                    role=user_data["role"],
                    is_active=True,
                    tenant_id=tenant.id,
                )
                session.add(user)
                all_users.append((tenant_data["name"], user_data))
                if tenant_admin is None:
                    tenant_admin = user
                print(f"  ✓ User: {user.username} ({user.role})")

            await session.flush()

            # Create contracts for this tenant
            for contract_data in tenant_data["contracts"]:
                contract = Contract(
                    id=uuid4(),
                    filename=contract_data["filename"],
                    file_path=f"/storage/uploads/{contract_data['filename']}",
                    file_size=245678,
                    mime_type="application/pdf",
                    status=contract_data["status"],
                    contract_type=contract_data["contract_type"],
                    counterparty=contract_data["counterparty"],
                    effective_date=today - timedelta(days=180),
                    expiration_date=today + timedelta(days=185),
                    contract_value=contract_data["contract_value"],
                    currency="USD" if contract_data["contract_value"] else None,
                    jurisdiction="Delaware, USA",
                    auto_renewal=True,
                    notice_period_days=60,
                    risk_level=contract_data["risk_level"],
                    risk_score=contract_data["risk_score"],
                    uploaded_by=tenant_admin.id,
                    tenant_id=tenant.id,
                )
                session.add(contract)
                print(f"  ✓ Contract: {contract.filename}")

                # Add clauses for completed contracts
                if contract.status == "completed":
                    await session.flush()
                    for clause_data in generate_sample_clauses(contract.id):
                        clause = Clause(**clause_data)
                        session.add(clause)

        # Create super admin (assign to first tenant for now)
        print(f"\n{'='*50}")
        print("Creating Super Admin")
        print('='*50)

        # Get first tenant for super admin
        first_tenant_id = (await session.execute(
            text("SELECT id FROM tenants LIMIT 1")
        )).scalar()

        superadmin = User(
            id=uuid4(),
            username=SUPER_ADMIN["username"],
            email=SUPER_ADMIN["email"],
            password_hash=hash_password(SUPER_ADMIN["password"]),
            role=SUPER_ADMIN["role"],
            is_active=True,
            tenant_id=first_tenant_id,
        )
        session.add(superadmin)
        print(f"  ✓ Super Admin: {superadmin.username}")

        # Commit all changes
        await session.commit()

    await engine.dispose()

    print("\n" + "="*60)
    print("✅ Database seeding completed successfully!")
    print("="*60)
    print("\nDemo Credentials:")
    print("-" * 60)
    print(f"{'Tenant':<15} {'Username':<20} {'Password':<15}")
    print("-" * 60)
    for tenant_name, user_data in all_users:
        print(f"{tenant_name:<15} {user_data['username']:<20} {user_data['password']:<15}")
    print(f"{'(Super Admin)':<15} {SUPER_ADMIN['username']:<20} {SUPER_ADMIN['password']:<15}")
    print("-" * 60)


if __name__ == "__main__":
    asyncio.run(seed_database())
