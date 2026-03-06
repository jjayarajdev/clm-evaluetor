"""Seed business units for all tenants."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session_maker
from app.models import Tenant
from app.models.business_unit import BusinessUnit


# Default business units to create for each tenant
DEFAULT_BUSINESS_UNITS = [
    {
        "name": "Legal",
        "code": "LEGAL",
        "description": "Legal Department - Contract review and compliance",
    },
    {
        "name": "Procurement",
        "code": "PROC",
        "description": "Procurement Department - Vendor management and purchasing",
    },
    {
        "name": "Sales",
        "code": "SALES",
        "description": "Sales Department - Customer contracts and agreements",
        "children": [
            {
                "name": "Enterprise Sales",
                "code": "SALES-ENT",
                "description": "Enterprise Sales Team",
            },
            {
                "name": "SMB Sales",
                "code": "SALES-SMB",
                "description": "Small and Medium Business Sales Team",
            },
        ],
    },
    {
        "name": "Operations",
        "code": "OPS",
        "description": "Operations Department - Service delivery and fulfillment",
    },
    {
        "name": "Finance",
        "code": "FIN",
        "description": "Finance Department - Financial contracts and agreements",
    },
]


async def create_bu_with_children(
    db, tenant_id: str, bu_data: dict, parent_id: str | None = None
) -> BusinessUnit:
    """Create a business unit and its children recursively."""
    children = bu_data.pop("children", [])

    # Check if BU already exists
    existing = await db.execute(
        select(BusinessUnit).where(
            BusinessUnit.tenant_id == tenant_id,
            BusinessUnit.code == bu_data["code"],
        )
    )
    bu = existing.scalar_one_or_none()

    if bu:
        print(f"  - {bu_data['name']} already exists")
    else:
        bu = BusinessUnit(
            tenant_id=tenant_id,
            parent_id=parent_id,
            **bu_data,
        )
        db.add(bu)
        await db.flush()  # Get the ID
        print(f"  + Created {bu_data['name']}")

    # Create children
    for child_data in children:
        await create_bu_with_children(db, tenant_id, child_data, bu.id)

    return bu


async def seed_business_units():
    """Seed business units for all tenants."""
    print("=" * 60)
    print("Seeding Business Units")
    print("=" * 60)

    async with async_session_maker() as db:
        # Get all tenants
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        if not tenants:
            print("No active tenants found.")
            return

        print(f"Found {len(tenants)} active tenant(s)\n")

        for tenant in tenants:
            print(f"\nTenant: {tenant.name}")
            print("-" * 40)

            for bu_data in DEFAULT_BUSINESS_UNITS:
                # Make a copy to avoid modifying the original
                bu_data_copy = bu_data.copy()
                if "children" in bu_data:
                    bu_data_copy["children"] = [c.copy() for c in bu_data["children"]]
                await create_bu_with_children(db, tenant.id, bu_data_copy)

        await db.commit()
        print("\n" + "=" * 60)
        print("Business unit seeding complete!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_business_units())
