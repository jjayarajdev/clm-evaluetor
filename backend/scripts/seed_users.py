"""Seed script to create default users."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database import async_session_maker, engine
from app.models.user import Role, User


async def create_default_users(db: AsyncSession) -> None:
    """Create default users if they don't exist."""

    default_users = [
        {
            "username": "superadmin",
            "email": "superadmin@contractintel.local",
            "password": "Super123!",
            "role": Role.SUPER_ADMIN,
        },
        {
            "username": "admin",
            "email": "admin@contractintel.local",
            "password": "Admin123!",
            "role": Role.ADMIN,
        },
        {
            "username": "legal",
            "email": "legal@contractintel.local",
            "password": "Legal123!",
            "role": Role.LEGAL,
        },
        {
            "username": "procurement",
            "email": "procurement@contractintel.local",
            "password": "Procure123!",
            "role": Role.PROCUREMENT,
        },
    ]

    for user_data in default_users:
        # Check if user already exists
        result = await db.execute(
            select(User).where(User.username == user_data["username"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"User '{user_data['username']}' already exists, skipping.")
            continue

        # Create new user
        user = User(
            username=user_data["username"],
            email=user_data["email"],
            password_hash=hash_password(user_data["password"]),
            role=user_data["role"],
            is_active=True,
        )
        db.add(user)
        print(f"Created user: {user_data['username']} ({user_data['role'].value})")

    await db.commit()


async def main() -> None:
    """Main entry point for seeding."""
    print("Seeding default users...")

    async with async_session_maker() as db:
        await create_default_users(db)

    print("Done!")

    # Print login credentials
    print("\n" + "=" * 50)
    print("Default Login Credentials:")
    print("=" * 50)
    print("Super Admin: superadmin / Super123!")
    print("Admin:       admin / Admin123!")
    print("Legal:       legal / Legal123!")
    print("Procurement: procurement / Procure123!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
