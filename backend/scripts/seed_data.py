#!/usr/bin/env python3
"""
Seed script to populate the database with sample data for development and testing.
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

from app.database import Base
from app.models import User, Contract, Clause, Obligation
from app.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


# Sample users - use enum values directly (lowercase strings) for PostgreSQL compatibility
SAMPLE_USERS = [
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "admin123",
        "role": "admin",
    },
    {
        "username": "legal",
        "email": "legal@example.com",
        "password": "legal123",
        "role": "legal",
    },
    {
        "username": "procurement",
        "email": "procurement@example.com",
        "password": "proc123",
        "role": "procurement",
    },
    {
        "username": "viewer",
        "email": "viewer@example.com",
        "password": "viewer123",
        "role": "viewer",
    },
]


# Sample contracts - use string values for PostgreSQL enum compatibility
def generate_sample_contracts(user_id) -> list[dict]:
    today = date.today()
    contracts = [
        {
            "id": uuid4(),
            "filename": "Master-Services-Agreement-Acme-Corp.pdf",
            "file_path": "/storage/uploads/sample1.pdf",
            "file_size": 245678,
            "mime_type": "application/pdf",
            "status": "completed",
            "contract_type": "msa",
            "counterparty": "Acme Corporation",
            "effective_date": today - timedelta(days=180),
            "expiration_date": today + timedelta(days=185),
            "contract_value": Decimal("500000.00"),
            "currency": "USD",
            "jurisdiction": "Delaware, USA",
            "auto_renewal": True,
            "notice_period_days": 60,
            "risk_level": "medium",
            "risk_score": 45,
            "uploaded_by": user_id,
        },
        {
            "id": uuid4(),
            "filename": "Software-License-Agreement-TechCo.docx",
            "file_path": "/storage/uploads/sample2.docx",
            "file_size": 189432,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "status": "completed",
            "contract_type": "sow",
            "counterparty": "TechCo Inc.",
            "effective_date": today - timedelta(days=90),
            "expiration_date": today + timedelta(days=275),
            "contract_value": Decimal("75000.00"),
            "currency": "USD",
            "jurisdiction": "California, USA",
            "auto_renewal": False,
            "notice_period_days": None,
            "risk_level": "low",
            "risk_score": 22,
            "uploaded_by": user_id,
        },
        {
            "id": uuid4(),
            "filename": "NDA-Strategic-Partner.pdf",
            "file_path": "/storage/uploads/sample3.pdf",
            "file_size": 98765,
            "mime_type": "application/pdf",
            "status": "completed",
            "contract_type": "nda",
            "counterparty": "Strategic Partners LLC",
            "effective_date": today - timedelta(days=30),
            "expiration_date": today + timedelta(days=335),
            "contract_value": None,
            "currency": None,
            "jurisdiction": "New York, USA",
            "auto_renewal": True,
            "notice_period_days": 30,
            "risk_level": "low",
            "risk_score": 15,
            "uploaded_by": user_id,
        },
        {
            "id": uuid4(),
            "filename": "Vendor-Agreement-GlobalSupply.pdf",
            "file_path": "/storage/uploads/sample4.pdf",
            "file_size": 312456,
            "mime_type": "application/pdf",
            "status": "completed",
            "contract_type": "vendor_agreement",
            "counterparty": "GlobalSupply International",
            "effective_date": today - timedelta(days=365),
            "expiration_date": today + timedelta(days=15),
            "contract_value": Decimal("1250000.00"),
            "currency": "USD",
            "jurisdiction": "Texas, USA",
            "auto_renewal": True,
            "notice_period_days": 90,
            "risk_level": "high",
            "risk_score": 72,
            "uploaded_by": user_id,
        },
        {
            "id": uuid4(),
            "filename": "Employment-Contract-Senior-Engineer.pdf",
            "file_path": "/storage/uploads/sample5.pdf",
            "file_size": 156789,
            "mime_type": "application/pdf",
            "status": "completed",
            "contract_type": "employment_contract",
            "counterparty": "John Smith",
            "effective_date": today - timedelta(days=60),
            "expiration_date": None,
            "contract_value": Decimal("180000.00"),
            "currency": "USD",
            "jurisdiction": "California, USA",
            "auto_renewal": False,
            "notice_period_days": None,
            "risk_level": "low",
            "risk_score": 18,
            "uploaded_by": user_id,
        },
        {
            "id": uuid4(),
            "filename": "Amendment-to-MSA-Acme.pdf",
            "file_path": "/storage/uploads/sample6.pdf",
            "file_size": 287654,
            "mime_type": "application/pdf",
            "status": "completed",
            "contract_type": "amendment",
            "counterparty": "Acme Corporation",
            "effective_date": today - timedelta(days=30),
            "expiration_date": today + timedelta(days=380),
            "contract_value": Decimal("150000.00"),
            "currency": "USD",
            "jurisdiction": "Delaware, USA",
            "auto_renewal": False,
            "notice_period_days": None,
            "risk_level": "critical",
            "risk_score": 85,
            "uploaded_by": user_id,
        },
        {
            "id": uuid4(),
            "filename": "Consulting-Agreement-Expert-Services.docx",
            "file_path": "/storage/uploads/sample7.docx",
            "file_size": 134567,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "status": "processing",
            "contract_type": None,
            "counterparty": None,
            "effective_date": None,
            "expiration_date": None,
            "contract_value": None,
            "currency": None,
            "jurisdiction": None,
            "auto_renewal": None,
            "notice_period_days": None,
            "risk_level": None,
            "risk_score": None,
            "uploaded_by": user_id,
        },
        {
            "id": uuid4(),
            "filename": "Partnership-Agreement-JointVenture.pdf",
            "file_path": "/storage/uploads/sample8.pdf",
            "file_size": 445678,
            "mime_type": "application/pdf",
            "status": "pending",
            "contract_type": None,
            "counterparty": None,
            "effective_date": None,
            "expiration_date": None,
            "contract_value": None,
            "currency": None,
            "jurisdiction": None,
            "auto_renewal": None,
            "notice_period_days": None,
            "risk_level": None,
            "risk_score": None,
            "uploaded_by": user_id,
        },
    ]
    return contracts


# Sample clauses for a contract - use string values for PostgreSQL enum compatibility
def generate_sample_clauses(contract_id) -> list[dict]:
    return [
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": "limitation_of_liability",
            "text": "Neither party shall be liable for any indirect, incidental, special, consequential, or punitive damages, regardless of the cause of action or the nature of the claim.",
            "summary": "Limitation of Liability - excludes consequential damages",
            "risk_level": "high",
            "risk_reason": "Broad limitation excludes consequential damages",
            "page_number": 8,
            "section_number": "12.1",
            "confidence_score": 0.92,
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": "indemnification",
            "text": "Customer shall indemnify, defend, and hold harmless Provider from any claims, damages, losses, and expenses arising from Customer's use of the Services.",
            "summary": "Indemnification - one-sided obligation on customer",
            "risk_level": "medium",
            "risk_reason": "One-sided indemnification favors provider",
            "page_number": 9,
            "section_number": "13.1",
            "confidence_score": 0.88,
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": "termination",
            "text": "Either party may terminate this Agreement for any reason upon 30 days written notice to the other party.",
            "summary": "Termination for convenience with 30 days notice",
            "risk_level": "low",
            "risk_reason": None,
            "page_number": 11,
            "section_number": "15.2",
            "confidence_score": 0.95,
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": "confidentiality",
            "text": "Each party agrees to maintain the confidentiality of all proprietary information received from the other party for a period of 5 years following disclosure.",
            "summary": "Mutual confidentiality for 5 years",
            "risk_level": "low",
            "risk_reason": None,
            "page_number": 6,
            "section_number": "8.1",
            "confidence_score": 0.91,
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "clause_type": "intellectual_property",
            "text": "All intellectual property developed by Provider in the performance of Services shall be the exclusive property of Provider.",
            "summary": "IP ownership retained by provider",
            "risk_level": "high",
            "risk_reason": "Provider retains all IP, no work-for-hire",
            "page_number": 7,
            "section_number": "10.1",
            "confidence_score": 0.87,
        },
    ]


# Sample obligations for a contract - use string values for PostgreSQL enum compatibility
def generate_sample_obligations(contract_id) -> list[dict]:
    today = date.today()
    return [
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "obligation_type": "payment",
            "description": "Quarterly payment of license fees due within 30 days of quarter end",
            "obligated_party": "Customer",
            "beneficiary_party": "Provider",
            "deadline_type": "recurring",
            "deadline": today + timedelta(days=30),
            "recurrence_pattern": "quarterly",
            "status": "pending",
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "obligation_type": "reporting",
            "description": "Monthly usage report submission to customer",
            "obligated_party": "Provider",
            "beneficiary_party": "Customer",
            "deadline_type": "recurring",
            "deadline": today + timedelta(days=7),
            "recurrence_pattern": "monthly",
            "status": "pending",
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "obligation_type": "compliance",
            "description": "Annual security audit completion and certification",
            "obligated_party": "Both Parties",
            "beneficiary_party": "Both Parties",
            "deadline_type": "recurring",
            "deadline": today + timedelta(days=90),
            "recurrence_pattern": "annually",
            "status": "pending",
        },
        {
            "id": uuid4(),
            "contract_id": contract_id,
            "obligation_type": "notification",
            "description": "Renewal notice deadline - must notify 60 days before expiration",
            "obligated_party": "Customer",
            "beneficiary_party": "Provider",
            "deadline_type": "fixed_date",
            "deadline": today + timedelta(days=125),
            "recurrence_pattern": None,
            "status": "pending",
        },
    ]


async def seed_database():
    """Seed the database with sample data."""
    print("Starting database seeding...")

    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)

    # Create session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create users
        print("Creating sample users...")
        users = []
        for user_data in SAMPLE_USERS:
            user = User(
                id=uuid4(),
                username=user_data["username"],
                email=user_data["email"],
                password_hash=hash_password(user_data["password"]),
                role=user_data["role"],
                is_active=True,
            )
            session.add(user)
            users.append(user)
            print(f"  Created user: {user.email} ({user.role})")

        await session.flush()

        # Create contracts (using admin user)
        admin_user = users[0]
        print("\nCreating sample contracts...")
        sample_contracts = generate_sample_contracts(admin_user.id)
        contracts = []

        for contract_data in sample_contracts:
            contract = Contract(**contract_data)
            session.add(contract)
            contracts.append(contract)
            print(f"  Created contract: {contract.filename} ({contract.status})")

        await session.flush()

        # Create clauses and obligations for completed contracts
        print("\nCreating sample clauses and obligations...")
        for contract in contracts:
            if contract.status == "completed":
                # Add clauses
                clauses = generate_sample_clauses(contract.id)
                for clause_data in clauses:
                    clause = Clause(**clause_data)
                    session.add(clause)

                # Add obligations
                obligations = generate_sample_obligations(contract.id)
                for obligation_data in obligations:
                    obligation = Obligation(**obligation_data)
                    session.add(obligation)

                print(f"  Added {len(clauses)} clauses and {len(obligations)} obligations to: {contract.filename}")

        # Commit all changes
        await session.commit()

    await engine.dispose()

    print("\n✅ Database seeding completed successfully!")
    print("\nSample credentials (username / password):")
    print("-" * 50)
    for user_data in SAMPLE_USERS:
        print(f"  {user_data['role']:12} | {user_data['username']:15} | {user_data['password']}")
    print("-" * 50)


if __name__ == "__main__":
    asyncio.run(seed_database())
