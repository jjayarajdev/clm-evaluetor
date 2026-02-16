#!/usr/bin/env python3
"""
Master Demo Seed Script - Populates the entire CLM system with realistic demo data.

This script creates a complete demo environment including:
- Users with different roles
- Clients and vendors (organizations)
- Contracts with various types and statuses
- Clauses, obligations, and SLAs
- Relationship governance data
- Sample SLA breaches and alerts

Run with: python -m scripts.seed_demo
Or: cd backend && uv run python -m scripts.seed_demo
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base

# Import all models
from app.models import User, Contract, Clause, Obligation
from app.models.client import Client
from app.models.sla import ContractSLA, SLAPerformance, SLAMetricType, SLAUnit, SLASeverity, BreachSeverity
from app.models.sla_alert import SLAAlert, AlertStatus, AlertCategory, AlertPriority


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ============================================================================
# SAMPLE DATA DEFINITIONS
# ============================================================================

DEMO_USERS = [
    {"username": "admin", "email": "admin@example.com", "password": "admin123", "role": "admin"},
    {"username": "sarah.legal", "email": "sarah@example.com", "password": "legal123", "role": "legal"},
    {"username": "mike.procurement", "email": "mike@example.com", "password": "proc123", "role": "procurement"},
    {"username": "jane.viewer", "email": "jane@example.com", "password": "viewer123", "role": "viewer"},
]

DEMO_CLIENTS = [
    {"name": "Acme Corporation", "code": "ACME", "industry": "Manufacturing", "country": "USA", "city": "Detroit"},
    {"name": "TechStart Inc", "code": "TECH", "industry": "Technology", "country": "USA", "city": "Austin"},
    {"name": "GlobalSupply International", "code": "GSI", "industry": "Logistics", "country": "Germany", "city": "Frankfurt"},
    {"name": "Innovation Labs", "code": "INLB", "industry": "Research", "country": "Singapore", "city": "Singapore"},
    {"name": "FinanceFirst Bank", "code": "FFB", "industry": "Financial Services", "country": "USA", "city": "New York"},
    {"name": "MediCare Plus", "code": "MCP", "industry": "Healthcare", "country": "USA", "city": "Boston"},
    {"name": "EuroTech GmbH", "code": "ETEC", "industry": "Technology", "country": "Germany", "city": "Munich"},
    {"name": "Pacific Trading Co", "code": "PTC", "industry": "Retail", "country": "Japan", "city": "Tokyo"},
]

DEMO_CONTRACTS = [
    # Strategic client contracts
    {"filename": "MSA_Acme_Corporation_2024.pdf", "type": "msa", "counterparty": "Acme Corporation", "value": 2500000, "risk": "medium", "status": "completed", "days_offset": -180, "expiry_days": 545},
    {"filename": "SOW_Acme_IT_Services.pdf", "type": "sow", "counterparty": "Acme Corporation", "value": 500000, "risk": "low", "status": "completed", "days_offset": -90, "expiry_days": 275},
    {"filename": "SOW_Acme_Digital_Transformation.pdf", "type": "sow", "counterparty": "Acme Corporation", "value": 750000, "risk": "medium", "status": "completed", "days_offset": -60, "expiry_days": 305},

    # Tech startup contracts
    {"filename": "MSA_TechStart_Cloud_Services.pdf", "type": "msa", "counterparty": "TechStart Inc", "value": 180000, "risk": "low", "status": "completed", "days_offset": -120, "expiry_days": 245},
    {"filename": "NDA_TechStart_Confidentiality.pdf", "type": "nda", "counterparty": "TechStart Inc", "value": None, "risk": "low", "status": "completed", "days_offset": -150, "expiry_days": 580},

    # High risk expiring soon
    {"filename": "Vendor_Agreement_GlobalSupply.pdf", "type": "vendor_agreement", "counterparty": "GlobalSupply International", "value": 1800000, "risk": "high", "status": "completed", "days_offset": -350, "expiry_days": 25},
    {"filename": "Amendment_GlobalSupply_Pricing.pdf", "type": "amendment", "counterparty": "GlobalSupply International", "value": 200000, "risk": "critical", "status": "completed", "days_offset": -30, "expiry_days": 60},

    # Finance client
    {"filename": "MSA_FinanceFirst_Banking.pdf", "type": "msa", "counterparty": "FinanceFirst Bank", "value": 3200000, "risk": "high", "status": "completed", "days_offset": -240, "expiry_days": 125},
    {"filename": "SOW_FinanceFirst_Support.pdf", "type": "sow", "counterparty": "FinanceFirst Bank", "value": 450000, "risk": "medium", "status": "completed", "days_offset": -200, "expiry_days": 165},

    # Healthcare
    {"filename": "MSA_MediCare_HIPAA_Compliant.pdf", "type": "msa", "counterparty": "MediCare Plus", "value": 890000, "risk": "medium", "status": "completed", "days_offset": -100, "expiry_days": 265},

    # Processing/pending contracts
    {"filename": "SOW_Innovation_Labs_Research.pdf", "type": "sow", "counterparty": "Innovation Labs", "value": 350000, "risk": None, "status": "processing", "days_offset": -2, "expiry_days": None},
    {"filename": "NDA_EuroTech_Partnership.pdf", "type": "nda", "counterparty": "EuroTech GmbH", "value": None, "risk": None, "status": "pending", "days_offset": 0, "expiry_days": None},

    # More variety
    {"filename": "SOW_Pacific_Trading_Consulting.pdf", "type": "sow", "counterparty": "Pacific Trading Co", "value": 125000, "risk": "low", "status": "completed", "days_offset": -45, "expiry_days": 320},
    {"filename": "MSA_TechStart_License.pdf", "type": "msa", "counterparty": "TechStart Inc", "value": 95000, "risk": "low", "status": "completed", "days_offset": -80, "expiry_days": 285},
    {"filename": "Employment_Contract_Senior_Architect.pdf", "type": "employment_contract", "counterparty": "John Williams", "value": 220000, "risk": "low", "status": "completed", "days_offset": -365, "expiry_days": None},
]

CLAUSE_TYPES = [
    ("limitation_of_liability", "high", "Broad limitation excludes consequential damages"),
    ("indemnification", "medium", "One-sided indemnification clause"),
    ("termination", "low", None),
    ("confidentiality", "low", None),
    ("intellectual_property", "medium", "IP ownership transfer required"),
    ("governing_law", "low", None),
    ("dispute_resolution", "medium", "Mandatory arbitration clause"),
    ("force_majeure", "low", None),
    ("payment_terms", "low", None),
    ("warranty", "medium", "Limited warranty period"),
]

OBLIGATION_TYPES = [
    ("payment", "Quarterly payment due within 30 days of quarter end", "recurring", "quarterly"),
    ("reporting", "Monthly usage report submission", "recurring", "monthly"),
    ("compliance", "Annual security audit and certification", "recurring", "annually"),
    ("notification", "Renewal notice deadline - 60 days before expiration", "fixed_date", None),
    ("delivery", "Deliver project milestone documentation", "fixed_date", None),
    ("performance", "Maintain performance standards per SLA", "recurring", "monthly"),
]


# ============================================================================
# SEED FUNCTIONS
# ============================================================================

async def clear_existing_data(session: AsyncSession):
    """Clear existing demo data (optional - be careful in production!)."""
    print("Clearing existing demo data...")
    # Note: In production, you'd want to be more selective
    await session.execute(text("DELETE FROM sla_alerts"))
    await session.execute(text("DELETE FROM sla_measurements"))
    await session.execute(text("DELETE FROM sla_metrics"))
    await session.execute(text("DELETE FROM slas"))
    await session.execute(text("DELETE FROM obligations"))
    await session.execute(text("DELETE FROM clauses"))
    await session.execute(text("DELETE FROM contracts"))
    await session.execute(text("DELETE FROM clients"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()
    print("  Cleared existing data")


async def seed_users(session: AsyncSession) -> dict:
    """Create demo users (or return existing) and return user map."""
    print("\nChecking demo users...")
    user_map = {}

    for user_data in DEMO_USERS:
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.username == user_data["username"])
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            user_map[user_data["username"]] = existing_user
            print(f"  Exists: {existing_user.username} ({existing_user.role})")
        else:
            user = User(
                id=uuid4(),
                username=user_data["username"],
                email=user_data["email"],
                password_hash=hash_password(user_data["password"]),
                role=user_data["role"],
                is_active=True,
            )
            session.add(user)
            user_map[user_data["username"]] = user
            print(f"  Created: {user.username} ({user.role})")

    await session.flush()
    return user_map


async def seed_clients(session: AsyncSession) -> dict:
    """Create demo clients (or return existing) and return client map."""
    print("\nChecking demo clients...")
    client_map = {}

    for client_data in DEMO_CLIENTS:
        # Check if client already exists
        result = await session.execute(
            select(Client).where(Client.code == client_data["code"])
        )
        existing_client = result.scalar_one_or_none()

        if existing_client:
            client_map[client_data["name"]] = existing_client
            print(f"  Exists: {existing_client.name} ({existing_client.code})")
        else:
            client = Client(
                id=uuid4(),
                name=client_data["name"],
                code=client_data["code"],
                industry=client_data["industry"],
                country=client_data["country"],
                city=client_data["city"],
                notes=f"Demo client - {client_data['industry']} sector",
            )
            session.add(client)
            client_map[client_data["name"]] = client
            print(f"  Created: {client.name} ({client.code})")

    await session.flush()
    return client_map


async def seed_contracts(session: AsyncSession, user_map: dict, client_map: dict) -> list:
    """Create demo contracts with clauses and obligations."""
    print("\nCreating demo contracts...")
    today = date.today()
    admin_user = user_map["admin"]
    contracts = []

    for contract_data in DEMO_CONTRACTS:
        # Find client if exists
        client = client_map.get(contract_data["counterparty"])

        # Calculate dates
        effective_date = today + timedelta(days=contract_data["days_offset"])
        expiry_date = today + timedelta(days=contract_data["expiry_days"]) if contract_data["expiry_days"] else None

        contract = Contract(
            id=uuid4(),
            filename=contract_data["filename"],
            file_path=f"/storage/uploads/{contract_data['filename']}",
            file_size=random.randint(100000, 500000),
            mime_type="application/pdf",
            status=contract_data["status"],
            contract_type=contract_data["type"],
            counterparty=contract_data["counterparty"],
            effective_date=effective_date,
            expiration_date=expiry_date,
            contract_value=Decimal(str(contract_data["value"])) if contract_data["value"] else None,
            currency="USD" if contract_data["value"] else None,
            jurisdiction="Delaware, USA",
            auto_renewal=random.choice([True, False]),
            notice_period_days=random.choice([30, 60, 90]) if expiry_date else None,
            risk_level=contract_data["risk"],
            risk_score={"low": 20, "medium": 50, "high": 75, "critical": 90}.get(contract_data["risk"]),
            uploaded_by=admin_user.id,
            client_id=client.id if client else None,
        )
        session.add(contract)
        contracts.append(contract)

        status_icon = {"completed": "✓", "processing": "⟳", "pending": "○"}.get(contract.status, "?")
        print(f"  {status_icon} {contract.filename} ({contract.contract_type})")

    await session.flush()
    return contracts


async def seed_clauses(session: AsyncSession, contracts: list):
    """Create demo clauses for completed contracts."""
    print("\nCreating demo clauses...")
    clause_count = 0

    for contract in contracts:
        if contract.status != "completed":
            continue

        # Add 3-6 clauses per contract
        num_clauses = random.randint(3, 6)
        selected_types = random.sample(CLAUSE_TYPES, min(num_clauses, len(CLAUSE_TYPES)))

        for i, (clause_type, risk_level, risk_reason) in enumerate(selected_types):
            clause = Clause(
                id=uuid4(),
                contract_id=contract.id,
                clause_type=clause_type,
                text=f"Sample {clause_type.replace('_', ' ')} clause text for {contract.counterparty}. "
                     f"This clause defines the terms and conditions related to {clause_type.replace('_', ' ')}.",
                summary=f"{clause_type.replace('_', ' ').title()} - standard terms",
                risk_level=risk_level,
                risk_reason=risk_reason,
                page_number=random.randint(1, 15),
                section_number=f"{random.randint(1, 20)}.{random.randint(1, 5)}",
                confidence_score=random.uniform(0.85, 0.98),
            )
            session.add(clause)
            clause_count += 1

    await session.flush()
    print(f"  Created {clause_count} clauses")


async def seed_obligations(session: AsyncSession, contracts: list):
    """Create demo obligations for completed contracts."""
    print("\nCreating demo obligations...")
    today = date.today()
    obligation_count = 0

    statuses = ["pending", "pending", "pending", "completed", "overdue", "in_progress"]

    for contract in contracts:
        if contract.status != "completed":
            continue

        # Add 2-4 obligations per contract
        num_obligations = random.randint(2, 4)
        selected_types = random.sample(OBLIGATION_TYPES, min(num_obligations, len(OBLIGATION_TYPES)))

        for ob_type, description, deadline_type, recurrence in selected_types:
            status = random.choice(statuses)

            # Set deadline based on status
            if status == "overdue":
                deadline = today - timedelta(days=random.randint(1, 30))
            elif status == "at_risk":
                deadline = today + timedelta(days=random.randint(1, 7))
            elif status == "completed":
                deadline = today - timedelta(days=random.randint(1, 60))
            else:
                deadline = today + timedelta(days=random.randint(7, 90))

            obligation = Obligation(
                id=uuid4(),
                contract_id=contract.id,
                obligation_type=ob_type,
                description=description,
                obligated_party=random.choice(["Customer", "Provider", "Both Parties"]),
                beneficiary_party=random.choice(["Customer", "Provider", "Both Parties"]),
                deadline_type=deadline_type,
                deadline=deadline,
                recurrence_pattern=recurrence,
                status=status,
                rag_status="green" if status == "completed" else ("red" if status == "overdue" else ("amber" if status == "in_progress" else "green")),
            )
            session.add(obligation)
            obligation_count += 1

    await session.flush()
    print(f"  Created {obligation_count} obligations")


async def seed_slas(session: AsyncSession, contracts: list):
    """Create demo SLAs for SOW contracts (service agreements)."""
    print("\nCreating demo SLAs...")
    sla_count = 0

    # Create SLAs for SOW contracts (service-related)
    sla_contracts = [c for c in contracts if c.contract_type == "sow" and c.status == "completed"][:3]

    sla_definitions = [
        ("System Uptime", SLAMetricType.UPTIME_PERCENTAGE, 99.9, SLAUnit.PERCENTAGE, SLASeverity.CRITICAL),
        ("P1 Response Time", SLAMetricType.RESPONSE_TIME, 15, SLAUnit.MINUTES, SLASeverity.CRITICAL),
        ("P1 Resolution Time", SLAMetricType.RESOLUTION_TIME, 4, SLAUnit.HOURS, SLASeverity.CRITICAL),
    ]

    for contract in sla_contracts:
        for sla_name, metric_type, target, metric_unit, severity in sla_definitions:
            sla = ContractSLA(
                id=uuid4(),
                contract_id=contract.id,
                sla_name=sla_name,
                sla_description=f"{sla_name} for {contract.counterparty}",
                metric_type=metric_type,
                metric_unit=metric_unit,
                target_value=Decimal(str(target)),
                severity=severity,
                measurement_period="monthly",
            )
            session.add(sla)
            sla_count += 1

        print(f"  Created SLAs for: {contract.counterparty}")

    await session.flush()
    print(f"  Created {sla_count} SLA definitions")


async def seed_sla_alerts(session: AsyncSession, contracts: list):
    """Create demo SLA alerts for breaches."""
    print("\nCreating demo SLA alerts...")
    today = datetime.now()
    alert_count = 0

    alert_samples = [
        ("Critical SLA Breach", "System uptime dropped below 99.9% threshold", AlertPriority.CRITICAL, AlertCategory.SLA_BREACH),
        ("High Priority Breach", "P1 response time exceeded 15 minute target", AlertPriority.HIGH, AlertCategory.SLA_BREACH),
        ("SLA Warning", "Resolution time approaching threshold", AlertPriority.MEDIUM, AlertCategory.SLA_WARNING),
        ("Performance Notice", "Minor deviation in metrics", AlertPriority.LOW, AlertCategory.SLA_WARNING),
    ]

    sla_contracts = [c for c in contracts if c.contract_type == "sow" and c.status == "completed"][:3]

    for contract in sla_contracts:
        # Create 2-4 alerts per SLA contract
        num_alerts = random.randint(2, 4)

        for i in range(num_alerts):
            title, message, priority, category = random.choice(alert_samples)

            # Random status distribution
            status = random.choice([
                AlertStatus.ACTIVE, AlertStatus.ACTIVE, AlertStatus.ACTIVE,
                AlertStatus.ACKNOWLEDGED, AlertStatus.RESOLVED
            ])

            alert = SLAAlert(
                id=uuid4(),
                contract_id=contract.id,
                title=f"{title} - {contract.counterparty}",
                description=message,
                priority=priority,
                category=category,
                status=status,
                triggered_at=today - timedelta(hours=random.randint(1, 72)),
                acknowledged_at=today - timedelta(hours=random.randint(1, 24)) if status != AlertStatus.ACTIVE else None,
                resolved_at=today if status == AlertStatus.RESOLVED else None,
            )
            session.add(alert)
            alert_count += 1

    await session.flush()
    print(f"  Created {alert_count} SLA alerts")


async def seed_demo():
    """Main function to seed all demo data."""
    print("=" * 60)
    print("CLM Demo Data Seeding")
    print("=" * 60)

    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Optional: Clear existing data (comment out if you want to keep existing data)
            # await clear_existing_data(session)

            # Seed in order
            user_map = await seed_users(session)
            client_map = await seed_clients(session)
            contracts = await seed_contracts(session, user_map, client_map)
            await seed_clauses(session, contracts)
            await seed_obligations(session, contracts)
            await seed_slas(session, contracts)
            # Skip SLA alerts for now - they're created by the monitoring system
            # await seed_sla_alerts(session, contracts)
            print("\n(SLA alerts will be generated by the monitoring system)")

            # Commit all changes
            await session.commit()

        except Exception as e:
            await session.rollback()
            print(f"\nError: {e}")
            raise

    await engine.dispose()

    print("\n" + "=" * 60)
    print("Demo seeding completed successfully!")
    print("=" * 60)
    print("\nDemo Credentials:")
    print("-" * 40)
    for user in DEMO_USERS:
        print(f"  {user['role']:12} | {user['email']:25} | {user['password']}")
    print("-" * 40)
    print("\nSummary:")
    print(f"  Users:       {len(DEMO_USERS)}")
    print(f"  Clients:     {len(DEMO_CLIENTS)}")
    print(f"  Contracts:   {len(DEMO_CONTRACTS)}")
    print("\nStart the app and login at http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(seed_demo())
