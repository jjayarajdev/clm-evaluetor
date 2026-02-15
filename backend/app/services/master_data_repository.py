"""Master Data Repository.

Provides database access for SLA and Milestone master data configurations.
Includes fallback to stub data if database is empty, and auto-seed functionality.
"""

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master_data import MilestoneMasterData, SLAMasterData

# Import stub configurations for seeding and fallback
from app.connectors.servicenow_stub import SLA_CONFIGURATIONS
from app.connectors.milestone_stub import MILESTONE_CONFIGURATIONS

logger = logging.getLogger(__name__)


class MasterDataRepository:
    """Repository for master data (SLA and Milestone configurations)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========================================================================
    # SLA Master Data Operations
    # ========================================================================

    async def get_sla_configs(self, active_only: bool = True) -> dict[str, dict]:
        """Get SLA configurations as a dictionary keyed by reference code.

        Returns format compatible with connector stubs.

        Args:
            active_only: If True, only return active configurations.

        Returns:
            Dict mapping reference_code to configuration dict.
        """
        query = select(SLAMasterData)
        if active_only:
            query = query.where(SLAMasterData.is_active == True)

        result = await self.db.execute(query)
        slas = result.scalars().all()

        # If no data in DB, fall back to stub configurations
        if not slas:
            logger.warning("No SLA master data in database, using stub configurations")
            return SLA_CONFIGURATIONS

        return {sla.reference_code: sla.to_config_dict() for sla in slas}

    async def get_sla_config_by_code(self, reference_code: str) -> dict | None:
        """Get a single SLA configuration by reference code.

        Args:
            reference_code: SLA reference code (e.g., "12.1").

        Returns:
            Configuration dict or None if not found.
        """
        result = await self.db.execute(
            select(SLAMasterData).where(SLAMasterData.reference_code == reference_code)
        )
        sla = result.scalars().first()

        if sla:
            return sla.to_config_dict()

        # Fallback to stub
        return SLA_CONFIGURATIONS.get(reference_code)

    async def get_all_sla_master_data(
        self,
        active_only: bool = False,
        category: str | None = None,
        service_tower: str | None = None,
    ) -> list[SLAMasterData]:
        """Get all SLA master data records.

        Args:
            active_only: Filter to active only.
            category: Filter by category.
            service_tower: Filter by service tower.

        Returns:
            List of SLAMasterData models.
        """
        query = select(SLAMasterData)

        if active_only:
            query = query.where(SLAMasterData.is_active == True)
        if category:
            query = query.where(SLAMasterData.category == category)
        if service_tower:
            query = query.where(SLAMasterData.service_tower == service_tower)

        query = query.order_by(SLAMasterData.reference_code)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_sla_by_id(self, sla_id: str) -> SLAMasterData | None:
        """Get SLA master data by ID."""
        result = await self.db.execute(
            select(SLAMasterData).where(SLAMasterData.id == sla_id)
        )
        return result.scalars().first()

    async def create_sla(self, data: dict) -> SLAMasterData:
        """Create a new SLA master data entry."""
        sla = SLAMasterData(**data)
        self.db.add(sla)
        await self.db.flush()
        await self.db.refresh(sla)
        return sla

    async def update_sla(self, sla_id: str, data: dict) -> SLAMasterData | None:
        """Update an SLA master data entry."""
        sla = await self.get_sla_by_id(sla_id)
        if not sla:
            return None

        for key, value in data.items():
            if hasattr(sla, key) and value is not None:
                setattr(sla, key, value)

        await self.db.flush()
        await self.db.refresh(sla)
        return sla

    async def delete_sla(self, sla_id: str) -> bool:
        """Delete an SLA master data entry."""
        sla = await self.get_sla_by_id(sla_id)
        if not sla:
            return False

        await self.db.delete(sla)
        await self.db.flush()
        return True

    async def count_sla_master_data(self) -> int:
        """Get count of SLA master data records."""
        result = await self.db.execute(select(func.count(SLAMasterData.id)))
        return result.scalar() or 0

    async def seed_sla_from_stubs(self) -> tuple[int, int]:
        """Seed SLA master data from stub configurations.

        Returns:
            Tuple of (seeded_count, skipped_count).
        """
        seeded = 0
        skipped = 0

        for ref_code, config in SLA_CONFIGURATIONS.items():
            # Check if already exists
            existing = await self.db.execute(
                select(SLAMasterData).where(SLAMasterData.reference_code == ref_code)
            )
            if existing.scalars().first():
                skipped += 1
                continue

            # Create new entry
            sla = SLAMasterData(
                reference_code=ref_code,
                name=config["name"],
                target_value=config["target"],
                minimum_value=config.get("minimum"),
                typical_performance=config.get("typical_performance"),
                volatility=config.get("volatility"),
                is_active=True,
            )
            self.db.add(sla)
            seeded += 1

        if seeded > 0:
            await self.db.flush()

        logger.info(f"SLA seed complete: {seeded} seeded, {skipped} skipped")
        return seeded, skipped

    # ========================================================================
    # Milestone Master Data Operations
    # ========================================================================

    async def get_milestone_configs(self, active_only: bool = True) -> dict[str, dict]:
        """Get Milestone configurations as a dictionary keyed by milestone code.

        Returns format compatible with connector stubs.

        Args:
            active_only: If True, only return active configurations.

        Returns:
            Dict mapping milestone_code to configuration dict.
        """
        query = select(MilestoneMasterData)
        if active_only:
            query = query.where(MilestoneMasterData.is_active == True)

        result = await self.db.execute(query)
        milestones = result.scalars().all()

        # If no data in DB, fall back to stub configurations
        if not milestones:
            logger.warning("No Milestone master data in database, using stub configurations")
            return MILESTONE_CONFIGURATIONS

        return {ms.milestone_code: ms.to_config_dict() for ms in milestones}

    async def get_milestone_config_by_code(self, milestone_code: str) -> dict | None:
        """Get a single Milestone configuration by code.

        Args:
            milestone_code: Milestone code (e.g., "MS-2.1").

        Returns:
            Configuration dict or None if not found.
        """
        result = await self.db.execute(
            select(MilestoneMasterData).where(MilestoneMasterData.milestone_code == milestone_code)
        )
        milestone = result.scalars().first()

        if milestone:
            return milestone.to_config_dict()

        # Fallback to stub
        return MILESTONE_CONFIGURATIONS.get(milestone_code)

    async def get_all_milestone_master_data(
        self,
        active_only: bool = False,
    ) -> list[MilestoneMasterData]:
        """Get all Milestone master data records.

        Args:
            active_only: Filter to active only.

        Returns:
            List of MilestoneMasterData models.
        """
        query = select(MilestoneMasterData)

        if active_only:
            query = query.where(MilestoneMasterData.is_active == True)

        query = query.order_by(MilestoneMasterData.baseline_days_from_start)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_milestone_by_id(self, milestone_id: str) -> MilestoneMasterData | None:
        """Get Milestone master data by ID."""
        result = await self.db.execute(
            select(MilestoneMasterData).where(MilestoneMasterData.id == milestone_id)
        )
        return result.scalars().first()

    async def create_milestone(self, data: dict) -> MilestoneMasterData:
        """Create a new Milestone master data entry."""
        milestone = MilestoneMasterData(**data)
        self.db.add(milestone)
        await self.db.flush()
        await self.db.refresh(milestone)
        return milestone

    async def update_milestone(self, milestone_id: str, data: dict) -> MilestoneMasterData | None:
        """Update a Milestone master data entry."""
        milestone = await self.get_milestone_by_id(milestone_id)
        if not milestone:
            return None

        for key, value in data.items():
            if hasattr(milestone, key) and value is not None:
                setattr(milestone, key, value)

        await self.db.flush()
        await self.db.refresh(milestone)
        return milestone

    async def delete_milestone(self, milestone_id: str) -> bool:
        """Delete a Milestone master data entry."""
        milestone = await self.get_milestone_by_id(milestone_id)
        if not milestone:
            return False

        await self.db.delete(milestone)
        await self.db.flush()
        return True

    async def count_milestone_master_data(self) -> int:
        """Get count of Milestone master data records."""
        result = await self.db.execute(select(func.count(MilestoneMasterData.id)))
        return result.scalar() or 0

    async def seed_milestones_from_stubs(self) -> tuple[int, int]:
        """Seed Milestone master data from stub configurations.

        Returns:
            Tuple of (seeded_count, skipped_count).
        """
        seeded = 0
        skipped = 0

        for ms_code, config in MILESTONE_CONFIGURATIONS.items():
            # Check if already exists
            existing = await self.db.execute(
                select(MilestoneMasterData).where(MilestoneMasterData.milestone_code == ms_code)
            )
            if existing.scalars().first():
                skipped += 1
                continue

            # Create new entry
            milestone = MilestoneMasterData(
                milestone_code=ms_code,
                name=config["name"],
                description=config.get("description"),
                baseline_days_from_start=config["baseline_days_from_start"],
                dependencies=config.get("dependencies", []),
                credit_at_risk=config.get("credit_at_risk"),
                is_active=True,
            )
            self.db.add(milestone)
            seeded += 1

        if seeded > 0:
            await self.db.flush()

        logger.info(f"Milestone seed complete: {seeded} seeded, {skipped} skipped")
        return seeded, skipped

    # ========================================================================
    # Combined Operations
    # ========================================================================

    async def seed_all_from_stubs(self) -> dict:
        """Seed both SLA and Milestone master data from stubs.

        Returns:
            Dict with seed results for both types.
        """
        sla_seeded, sla_skipped = await self.seed_sla_from_stubs()
        ms_seeded, ms_skipped = await self.seed_milestones_from_stubs()

        return {
            "sla": {"seeded": sla_seeded, "skipped": sla_skipped},
            "milestones": {"seeded": ms_seeded, "skipped": ms_skipped},
        }

    async def is_data_seeded(self) -> bool:
        """Check if master data has been seeded."""
        sla_count = await self.count_sla_master_data()
        ms_count = await self.count_milestone_master_data()
        return sla_count > 0 or ms_count > 0


async def get_master_data_repository(db: AsyncSession) -> MasterDataRepository:
    """Factory function for MasterDataRepository."""
    return MasterDataRepository(db)


async def auto_seed_master_data(db: AsyncSession) -> dict | None:
    """Auto-seed master data if not already seeded.

    Called on application startup.

    Args:
        db: Database session.

    Returns:
        Seed results if seeding occurred, None if already seeded.
    """
    repo = MasterDataRepository(db)

    if await repo.is_data_seeded():
        logger.info("Master data already seeded, skipping auto-seed")
        return None

    logger.info("Auto-seeding master data from stub configurations...")
    result = await repo.seed_all_from_stubs()
    await db.commit()
    logger.info(f"Master data auto-seed complete: {result}")
    return result
