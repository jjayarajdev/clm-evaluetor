"""Distribute contracts to business units and create external users."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.database import async_session_maker
from app.models import Tenant, User, Contract
from app.models.user import Role
from app.models.business_unit import BusinessUnit
from app.models.external_user import ExternalUser
from app.models.contract_share import ContractShare
from app.models.organization import Organization


async def distribute_contracts_to_business_units():
    """Assign contracts to business units for each tenant."""
    print("=" * 60)
    print("Distributing Contracts to Business Units")
    print("=" * 60)

    async with async_session_maker() as db:
        # Get all tenants
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        for tenant in tenants:
            print(f"\nTenant: {tenant.name}")
            print("-" * 40)

            # Get business units for this tenant
            bu_result = await db.execute(
                select(BusinessUnit).where(
                    BusinessUnit.tenant_id == tenant.id,
                    BusinessUnit.is_active == True
                )
            )
            business_units = bu_result.scalars().all()

            if not business_units:
                print("  No business units found, skipping...")
                continue

            # Get contracts for this tenant that don't have a business unit
            contract_result = await db.execute(
                select(Contract).where(
                    Contract.tenant_id == tenant.id,
                    Contract.business_unit_id == None
                )
            )
            contracts = contract_result.scalars().all()

            if not contracts:
                print("  All contracts already assigned to business units")
                continue

            print(f"  Found {len(contracts)} contracts to distribute across {len(business_units)} BUs")

            # Distribute contracts round-robin across business units
            for i, contract in enumerate(contracts):
                bu = business_units[i % len(business_units)]
                contract.business_unit_id = bu.id
                print(f"  + {contract.filename[:40]}... -> {bu.name}")

            await db.commit()
            print(f"  Distributed {len(contracts)} contracts")

    print("\n" + "=" * 60)
    print("Contract distribution complete!")
    print("=" * 60)


async def create_external_users():
    """Create external users (counterparty contacts) for each tenant."""
    print("\n" + "=" * 60)
    print("Creating External Users")
    print("=" * 60)

    # Sample external users to create
    EXTERNAL_USERS = [
        {
            "email": "john.smith@acmecorp.com",
            "full_name": "John Smith",
            "company_name": "Acme Corp",
            "title": "Procurement Manager",
        },
        {
            "email": "sarah.jones@techstart.io",
            "full_name": "Sarah Jones",
            "company_name": "TechStart",
            "title": "Legal Counsel",
        },
        {
            "email": "mike.wilson@globaltech.com",
            "full_name": "Mike Wilson",
            "company_name": "GlobalTech Inc",
            "title": "Contract Specialist",
        },
        {
            "email": "lisa.chen@innovate.co",
            "full_name": "Lisa Chen",
            "company_name": "Innovate Co",
            "title": "VP Legal",
        },
        {
            "email": "david.brown@enterprise.com",
            "full_name": "David Brown",
            "company_name": "Enterprise Solutions",
            "title": "Account Manager",
        },
    ]

    async with async_session_maker() as db:
        # Get all tenants
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        for tenant in tenants:
            print(f"\nTenant: {tenant.name}")
            print("-" * 40)

            # Get admin user for this tenant
            admin_result = await db.execute(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.role == Role.ADMIN,
                    User.is_active == True
                ).limit(1)
            )
            admin_user = admin_result.scalar_one_or_none()

            for user_data in EXTERNAL_USERS:
                # Check if external user exists
                ext_user_result = await db.execute(
                    select(ExternalUser).where(
                        ExternalUser.tenant_id == tenant.id,
                        ExternalUser.email == user_data["email"]
                    )
                )
                ext_user = ext_user_result.scalar_one_or_none()

                if ext_user:
                    print(f"  - External user {user_data['email']} already exists")
                else:
                    # Create external user
                    ext_user = ExternalUser(
                        tenant_id=tenant.id,
                        email=user_data["email"],
                        full_name=user_data["full_name"],
                        company_name=user_data["company_name"],
                        title=user_data.get("title"),
                        is_active=True,
                        invited_by_id=admin_user.id if admin_user else None,
                        invited_at=datetime.utcnow(),
                    )
                    db.add(ext_user)
                    print(f"  + Created external user: {user_data['full_name']} ({user_data['email']})")

            await db.commit()

    print("\n" + "=" * 60)
    print("External users created!")
    print("=" * 60)


async def share_contracts_with_external_users():
    """Share some contracts with external users."""
    print("\n" + "=" * 60)
    print("Sharing Contracts with External Users")
    print("=" * 60)

    async with async_session_maker() as db:
        # Get all tenants
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        for tenant in tenants:
            print(f"\nTenant: {tenant.name}")
            print("-" * 40)

            # Get admin user for this tenant to be the sharer
            admin_result = await db.execute(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.role == Role.ADMIN,
                    User.is_active == True
                ).limit(1)
            )
            admin_user = admin_result.scalar_one_or_none()

            if not admin_user:
                print("  No admin user found, skipping...")
                continue

            # Get external users for this tenant
            ext_users_result = await db.execute(
                select(ExternalUser).where(
                    ExternalUser.tenant_id == tenant.id,
                    ExternalUser.is_active == True
                )
            )
            external_users = ext_users_result.scalars().all()

            if not external_users:
                print("  No external users found, skipping...")
                continue

            # Get contracts for this tenant
            contracts_result = await db.execute(
                select(Contract).where(Contract.tenant_id == tenant.id).limit(10)
            )
            contracts = contracts_result.scalars().all()

            if not contracts:
                print("  No contracts found, skipping...")
                continue

            # Share first few contracts with external users
            shares_created = 0
            for i, contract in enumerate(contracts[:5]):
                ext_user = external_users[i % len(external_users)]

                # Check if share already exists
                share_result = await db.execute(
                    select(ContractShare).where(
                        ContractShare.contract_id == contract.id,
                        ContractShare.external_user_id == ext_user.id
                    )
                )
                existing_share = share_result.scalar_one_or_none()

                if existing_share:
                    continue

                # Create share
                share = ContractShare(
                    contract_id=contract.id,
                    external_user_id=ext_user.id,
                    shared_by_id=admin_user.id,
                    can_comment=True,
                    can_download=True,
                    expires_at=datetime.utcnow() + timedelta(days=90),
                )
                db.add(share)
                shares_created += 1
                print(f"  + Shared '{contract.filename[:30]}...' with {ext_user.full_name}")

            await db.commit()
            print(f"  Created {shares_created} contract shares")

    print("\n" + "=" * 60)
    print("Contract sharing complete!")
    print("=" * 60)


async def main():
    """Run all seeding operations."""
    await distribute_contracts_to_business_units()
    await create_external_users()
    await share_contracts_with_external_users()


if __name__ == "__main__":
    asyncio.run(main())
