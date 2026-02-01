#!/usr/bin/env python3
"""Clear all seed/mock data from the database, keeping only the admin user."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import async_session_maker


async def clear_seed_data():
    """Clear all seeded data from the database."""
    async with async_session_maker() as session:
        try:
            # Delete in order respecting foreign key constraints
            print("Clearing audit_logs...")
            await session.execute(text("DELETE FROM audit_logs"))

            print("Clearing alert_configs...")
            await session.execute(text("DELETE FROM alert_configs"))

            print("Clearing obligations...")
            await session.execute(text("DELETE FROM obligations"))

            print("Clearing clauses...")
            await session.execute(text("DELETE FROM clauses"))

            print("Clearing contracts...")
            await session.execute(text("DELETE FROM contracts"))

            # Keep admin user, delete others
            print("Removing non-admin users...")
            await session.execute(text("DELETE FROM users WHERE role != 'admin'"))

            await session.commit()
            print("\nAll mock data cleared successfully!")
            print("Admin user retained.")

            # Show remaining counts
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"\nRemaining users: {user_count}")

        except Exception as e:
            await session.rollback()
            print(f"Error clearing data: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(clear_seed_data())
