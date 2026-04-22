"""Seed BU-specific test users across all tenants and distribute contracts."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import Tenant, User, Contract
from app.models.user import Role
from app.models.business_unit import BusinessUnit


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Users to create per tenant: (username_suffix, full_name, role, bu_code)
BU_USERS = [
    ("procurement", "Procurement Manager", Role.PROCUREMENT, "PROC"),
    ("legal_bu", "Legal Counsel", Role.LEGAL, "LEGAL"),
    ("ops", "Operations Lead", Role.VIEWER, "OPS"),
    ("sales_head", "Sales Director", Role.BU_HEAD, "SALES"),
    ("finance", "Finance Analyst", Role.VIEWER, "FIN"),
]

PASSWORD = "demo123"

# Map tenant slug -> username prefix
TENANT_PREFIXES = {
    "acme": "acme",
    "techstart": "ts",
    "legalco": "lc",
}


async def seed_bu_users():
    """Create BU-specific users for all tenants."""
    print("=" * 60)
    print("Seeding BU Test Users")
    print("=" * 60)

    hashed = hash_password(PASSWORD)
    created_users = []

    async with async_session_maker() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        for tenant in tenants:
            prefix = TENANT_PREFIXES.get(tenant.slug, tenant.slug)
            print(f"\nTenant: {tenant.name} (prefix: {prefix})")
            print("-" * 40)

            # Load BUs for this tenant
            bu_result = await db.execute(
                select(BusinessUnit).where(
                    BusinessUnit.tenant_id == tenant.id,
                    BusinessUnit.is_active == True,
                )
            )
            bus = {bu.code: bu for bu in bu_result.scalars().all()}

            if not bus:
                print("  No BUs found — run seed_business_units first")
                continue

            for suffix, full_name, role, bu_code in BU_USERS:
                bu = bus.get(bu_code)
                if not bu:
                    print(f"  ! BU {bu_code} not found, skipping {suffix}")
                    continue

                username = f"{prefix}_{suffix}"
                email = f"{username}@{tenant.slug}.com"

                # Check if user already exists
                existing = await db.execute(
                    select(User).where(User.username == username)
                )
                if existing.scalar_one_or_none():
                    print(f"  - {username} already exists")
                    continue

                user = User(
                    username=username,
                    email=email,
                    full_name=f"{full_name} ({tenant.name})",
                    password_hash=hashed,
                    role=role,
                    tenant_id=tenant.id,
                    business_unit_id=bu.id,
                    is_active=True,
                )
                db.add(user)
                created_users.append((username, role.value, bu.name, tenant.name))
                print(f"  + {username:25s} {role.value:15s} -> {bu.name}")

        await db.commit()

    print("\n" + "=" * 60)
    print(f"Created {len(created_users)} users (password: {PASSWORD})")
    print("=" * 60)
    return created_users


async def distribute_contracts():
    """Distribute unassigned contracts across BUs per tenant."""
    print("\n" + "=" * 60)
    print("Distributing Contracts to Business Units")
    print("=" * 60)

    async with async_session_maker() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        for tenant in tenants:
            print(f"\nTenant: {tenant.name}")
            print("-" * 40)

            # Get BUs (only leaf-level for cleaner distribution)
            bu_result = await db.execute(
                select(BusinessUnit).where(
                    BusinessUnit.tenant_id == tenant.id,
                    BusinessUnit.is_active == True,
                )
            )
            bus = bu_result.scalars().all()

            if not bus:
                print("  No BUs found")
                continue

            # Get unassigned contracts
            contract_result = await db.execute(
                select(Contract).where(
                    Contract.tenant_id == tenant.id,
                    Contract.business_unit_id == None,
                )
            )
            contracts = contract_result.scalars().all()

            if not contracts:
                # Count existing distribution
                count_result = await db.execute(
                    select(
                        BusinessUnit.name,
                        func.count(Contract.id),
                    )
                    .join(Contract, Contract.business_unit_id == BusinessUnit.id)
                    .where(BusinessUnit.tenant_id == tenant.id)
                    .group_by(BusinessUnit.name)
                )
                rows = count_result.all()
                if rows:
                    print("  Already distributed:")
                    for bu_name, count in rows:
                        print(f"    {bu_name}: {count} contracts")
                else:
                    print("  No contracts found")
                continue

            print(f"  Distributing {len(contracts)} contracts across {len(bus)} BUs:")

            for i, contract in enumerate(contracts):
                bu = bus[i % len(bus)]
                contract.business_unit_id = bu.id

            await db.commit()

            # Print distribution summary
            count_result = await db.execute(
                select(
                    BusinessUnit.name,
                    func.count(Contract.id),
                )
                .join(Contract, Contract.business_unit_id == BusinessUnit.id)
                .where(BusinessUnit.tenant_id == tenant.id)
                .group_by(BusinessUnit.name)
            )
            for bu_name, count in count_result.all():
                print(f"    {bu_name}: {count} contracts")

    print("\n" + "=" * 60)
    print("Distribution complete!")
    print("=" * 60)


async def print_login_table():
    """Print a summary table of all BU users for easy reference."""
    print("\n" + "=" * 70)
    print("LOGIN REFERENCE TABLE")
    print("=" * 70)
    print(f"{'Username':25s} {'Password':10s} {'Role':15s} {'BU':15s} {'Tenant'}")
    print("-" * 70)

    async with async_session_maker() as db:
        result = await db.execute(
            select(User, BusinessUnit.name, Tenant.name)
            .outerjoin(BusinessUnit, User.business_unit_id == BusinessUnit.id)
            .outerjoin(Tenant, User.tenant_id == Tenant.id)
            .where(User.business_unit_id != None)
            .order_by(Tenant.name, BusinessUnit.name)
        )
        rows = result.all()

        for user, bu_name, tenant_name in rows:
            print(
                f"{user.username:25s} {PASSWORD:10s} {user.role.value:15s} {bu_name or '-':15s} {tenant_name or '-'}"
            )

    print("=" * 70)


async def main():
    await seed_bu_users()
    await distribute_contracts()
    await print_login_table()


if __name__ == "__main__":
    asyncio.run(main())
