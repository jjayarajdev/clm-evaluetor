"""Synthetic Data Generator for testing the Actionable Contracts system.

Generates realistic test data including:
- SLA measurements (with breaches and warnings)
- Upcoming renewals
- Overdue milestones
- Due obligations
"""

import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract, ContractStatus
from app.models.integration import SLAMeasurement
from app.models.key_date import ContractKeyDate, DateEventType
from app.models.obligation import Obligation, ObligationStatus
from app.models.sla import ContractSLA, SLAPerformance, BreachSeverity

logger = logging.getLogger(__name__)


class SyntheticDataGenerator:
    """Generates synthetic test data for contract monitoring.

    Creates realistic scenarios that will trigger the event detection
    and workflow execution systems.
    """

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def generate_all(
        self,
        breach_count: int = 3,
        warning_count: int = 2,
    ) -> dict:
        """Generate all types of test data.

        Args:
            breach_count: Number of SLA breaches to generate.
            warning_count: Number of SLA warnings to generate.

        Returns:
            Summary of generated data.
        """
        logger.info("Generating synthetic test data")

        results = {
            "sla_measurements": 0,
            "sla_breaches": 0,
            "sla_warnings": 0,
            "milestones": 0,
            "obligations": 0,
        }

        # Get active contracts with SLAs
        contracts = await self._get_contracts_with_slas()

        if not contracts:
            logger.warning("No contracts with SLAs found. Cannot generate data.")
            return results

        # Generate SLA measurements
        measurements, breaches = await self.generate_sla_measurements(
            contracts,
            breach_count=breach_count,
            warning_count=warning_count,
        )
        results["sla_measurements"] = measurements
        results["sla_breaches"] = breaches

        logger.info(f"Synthetic data generation complete: {results}")
        return results

    async def generate_sla_measurements(
        self,
        contracts: list[Contract],
        breach_count: int = 3,
        warning_count: int = 2,
    ) -> tuple[int, int]:
        """Generate SLA measurement records including breaches.

        Args:
            contracts: Contracts to generate measurements for.
            breach_count: Number of breach measurements to create.
            warning_count: Number of warning-level measurements.

        Returns:
            Tuple of (total_measurements, breaches).
        """
        logger.info(f"Generating SLA measurements for {len(contracts)} contracts")

        total_measurements = 0
        total_breaches = 0

        # Get all SLAs for these contracts
        contract_ids = [c.id for c in contracts]
        sla_query = select(ContractSLA).where(
            ContractSLA.contract_id.in_(contract_ids),
            ContractSLA.is_active == True,
        )
        result = await self.db.execute(sla_query)
        slas = result.scalars().all()

        if not slas:
            logger.warning("No active SLAs found")
            return 0, 0

        # Randomly select SLAs for breaches
        breach_slas = random.sample(slas, min(breach_count, len(slas)))

        # Generate breach measurements
        for sla in breach_slas:
            measurement = await self._create_breach_measurement(sla)
            if measurement:
                total_measurements += 1
                total_breaches += 1

        # Generate warning measurements for remaining SLAs
        remaining_slas = [s for s in slas if s not in breach_slas]
        warning_slas = random.sample(remaining_slas, min(warning_count, len(remaining_slas)))

        for sla in warning_slas:
            measurement = await self._create_warning_measurement(sla)
            if measurement:
                total_measurements += 1

        # Generate normal measurements for some SLAs
        normal_slas = [s for s in slas if s not in breach_slas and s not in warning_slas]
        for sla in normal_slas[:5]:  # Limit to 5 normal measurements
            measurement = await self._create_normal_measurement(sla)
            if measurement:
                total_measurements += 1

        await self.db.commit()
        return total_measurements, total_breaches

    async def _create_breach_measurement(self, sla: ContractSLA) -> Optional[SLAMeasurement]:
        """Create a breach measurement for an SLA.

        Args:
            sla: The SLA to create a breach for.

        Returns:
            The created measurement or None.
        """
        target = float(sla.target_value)
        operator = sla.target_operator

        # Calculate a breach value
        if operator in (">=", ">"):
            # For uptime-style (higher is better), go below target
            deviation = random.uniform(5, 25)  # 5-25% below
            actual = target * (1 - deviation / 100)
        else:
            # For error-rate style (lower is better), go above target
            deviation = random.uniform(50, 200)  # 50-200% above
            actual = target * (1 + deviation / 100)

        now = datetime.utcnow()
        period_end = now - timedelta(hours=random.randint(1, 24))
        period_start = period_end - timedelta(days=30)

        measurement = SLAMeasurement(
            sla_id=sla.id,
            measurement_date=now,
            period_start=period_start,
            period_end=period_end,
            actual_value=round(actual, 2),
            target_value=float(sla.target_value),
            is_breach=True,
            deviation_percent=round(deviation, 2),
            source="synthetic",
            source_reference=f"synthetic-breach-{now.strftime('%Y%m%d%H%M%S')}",
            event_generated=False,
        )

        self.db.add(measurement)

        # Update SLA consecutive breaches
        sla.consecutive_breaches += 1
        sla.current_compliance_rate = Decimal(str(round(actual, 2)))
        sla.last_measured_at = now

        logger.info(f"Created breach measurement for SLA {sla.sla_name}: {actual:.2f} vs {target:.2f}")
        return measurement

    async def _create_warning_measurement(self, sla: ContractSLA) -> Optional[SLAMeasurement]:
        """Create a warning-level measurement (approaching breach).

        Args:
            sla: The SLA to create a warning for.

        Returns:
            The created measurement or None.
        """
        target = float(sla.target_value)
        warning = float(sla.warning_threshold) if sla.warning_threshold else target * 0.95
        operator = sla.target_operator

        # Value between warning and target
        if operator in (">=", ">"):
            actual = random.uniform(warning, target - 0.1)
        else:
            actual = random.uniform(target + 0.1, warning)

        now = datetime.utcnow()

        measurement = SLAMeasurement(
            sla_id=sla.id,
            measurement_date=now,
            period_start=now - timedelta(days=30),
            period_end=now,
            actual_value=round(actual, 2),
            target_value=target,
            is_breach=False,
            deviation_percent=round(abs((target - actual) / target * 100), 2),
            source="synthetic",
            source_reference=f"synthetic-warning-{now.strftime('%Y%m%d%H%M%S')}",
            event_generated=False,
        )

        self.db.add(measurement)

        # Update SLA current compliance
        sla.current_compliance_rate = Decimal(str(round(actual, 2)))
        sla.last_measured_at = now

        logger.info(f"Created warning measurement for SLA {sla.sla_name}: {actual:.2f}")
        return measurement

    async def _create_normal_measurement(self, sla: ContractSLA) -> Optional[SLAMeasurement]:
        """Create a normal (compliant) measurement.

        Args:
            sla: The SLA to create a measurement for.

        Returns:
            The created measurement or None.
        """
        target = float(sla.target_value)
        operator = sla.target_operator

        # Exceed target slightly
        if operator in (">=", ">"):
            actual = target + random.uniform(0.5, 3)
        else:
            actual = target - random.uniform(0.1, 1)

        now = datetime.utcnow()

        measurement = SLAMeasurement(
            sla_id=sla.id,
            measurement_date=now,
            period_start=now - timedelta(days=30),
            period_end=now,
            actual_value=round(actual, 2),
            target_value=target,
            is_breach=False,
            deviation_percent=0,
            source="synthetic",
            event_generated=False,
        )

        self.db.add(measurement)

        # Update SLA
        sla.current_compliance_rate = Decimal(str(round(actual, 2)))
        sla.last_measured_at = now

        return measurement

    async def _get_contracts_with_slas(self) -> list[Contract]:
        """Get active contracts that have SLAs defined."""
        query = (
            select(Contract)
            .where(Contract.status == ContractStatus.active)
            .limit(20)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_test_scenario(
        self,
        scenario_type: str = "sla_breach"
    ) -> dict:
        """Create a specific test scenario.

        Args:
            scenario_type: Type of scenario to create.
                Options: sla_breach, sla_warning, renewal, milestone_overdue

        Returns:
            Details of the created scenario.
        """
        logger.info(f"Creating test scenario: {scenario_type}")

        if scenario_type == "sla_breach":
            return await self._create_sla_breach_scenario()
        elif scenario_type == "sla_warning":
            return await self._create_sla_warning_scenario()
        elif scenario_type == "renewal":
            return await self._create_renewal_scenario()
        elif scenario_type == "milestone_overdue":
            return await self._create_milestone_overdue_scenario()
        else:
            raise ValueError(f"Unknown scenario type: {scenario_type}")

    async def _create_sla_breach_scenario(self) -> dict:
        """Create a complete SLA breach test scenario.

        This creates a breach measurement that will trigger:
        1. Event detection
        2. Workflow execution
        3. Service credit calculation
        4. Approval request
        5. Notifications
        """
        contracts = await self._get_contracts_with_slas()
        if not contracts:
            raise ValueError("No contracts with SLAs available")

        # Get an SLA for breach
        sla_query = select(ContractSLA).where(
            ContractSLA.contract_id == contracts[0].id,
            ContractSLA.is_active == True,
        ).limit(1)
        result = await self.db.execute(sla_query)
        sla = result.scalar_one_or_none()

        if not sla:
            raise ValueError("No active SLA found for contract")

        measurement = await self._create_breach_measurement(sla)
        await self.db.commit()

        return {
            "scenario_type": "sla_breach",
            "contract_id": str(contracts[0].id),
            "contract_name": contracts[0].filename,
            "sla_id": str(sla.id),
            "sla_name": sla.sla_name,
            "measurement_id": str(measurement.id) if measurement else None,
            "target_value": float(sla.target_value),
            "actual_value": float(measurement.actual_value) if measurement else None,
            "deviation": float(measurement.deviation_percent) if measurement else None,
            "message": "SLA breach scenario created. Run event detection to trigger workflow.",
        }

    async def _create_sla_warning_scenario(self) -> dict:
        """Create an SLA warning scenario."""
        contracts = await self._get_contracts_with_slas()
        if not contracts:
            raise ValueError("No contracts with SLAs available")

        sla_query = select(ContractSLA).where(
            ContractSLA.contract_id == contracts[0].id,
            ContractSLA.is_active == True,
            ContractSLA.warning_threshold.isnot(None),
        ).limit(1)
        result = await self.db.execute(sla_query)
        sla = result.scalar_one_or_none()

        if not sla:
            # Use any SLA
            sla_query = select(ContractSLA).where(
                ContractSLA.contract_id == contracts[0].id,
                ContractSLA.is_active == True,
            ).limit(1)
            result = await self.db.execute(sla_query)
            sla = result.scalar_one_or_none()

        if not sla:
            raise ValueError("No SLA found")

        measurement = await self._create_warning_measurement(sla)
        await self.db.commit()

        return {
            "scenario_type": "sla_warning",
            "contract_id": str(contracts[0].id),
            "sla_id": str(sla.id),
            "sla_name": sla.sla_name,
            "measurement_id": str(measurement.id) if measurement else None,
            "message": "SLA warning scenario created.",
        }

    async def _create_renewal_scenario(self) -> dict:
        """Create a contract approaching renewal scenario."""
        # Find a contract and update its expiration date
        query = select(Contract).where(
            Contract.status == ContractStatus.active
        ).limit(1)
        result = await self.db.execute(query)
        contract = result.scalar_one_or_none()

        if not contract:
            raise ValueError("No active contract found")

        # Set expiration to 30 days from now
        contract.expiration_date = (datetime.utcnow() + timedelta(days=30)).date()
        await self.db.commit()

        return {
            "scenario_type": "renewal",
            "contract_id": str(contract.id),
            "contract_name": contract.filename,
            "expiration_date": contract.expiration_date.isoformat(),
            "days_until": 30,
            "message": "Renewal scenario created.",
        }

    async def _create_milestone_overdue_scenario(self) -> dict:
        """Create an overdue milestone scenario."""
        # Find a contract
        query = select(Contract).where(
            Contract.status == ContractStatus.active
        ).limit(1)
        result = await self.db.execute(query)
        contract = result.scalar_one_or_none()

        if not contract:
            raise ValueError("No active contract found")

        # Create an overdue key date
        overdue_date = (datetime.utcnow() - timedelta(days=5)).date()

        key_date = ContractKeyDate(
            contract_id=contract.id,
            event_name="Q4 Deliverable Review",
            event_date=overdue_date,
            event_type=DateEventType.MILESTONE,
            description="Quarterly deliverable review and sign-off",
            is_completed=False,
            responsible_party="Vendor",
        )
        self.db.add(key_date)
        await self.db.commit()

        return {
            "scenario_type": "milestone_overdue",
            "contract_id": str(contract.id),
            "contract_name": contract.filename,
            "key_date_id": str(key_date.id),
            "milestone_name": key_date.event_name,
            "due_date": overdue_date.isoformat(),
            "days_overdue": 5,
            "message": "Milestone overdue scenario created.",
        }


async def generate_test_data(db: AsyncSession, scenario: Optional[str] = None) -> dict:
    """Convenience function to generate test data.

    Args:
        db: Database session.
        scenario: Optional specific scenario to create.

    Returns:
        Generation results.
    """
    generator = SyntheticDataGenerator(db)

    if scenario:
        return await generator.create_test_scenario(scenario)
    else:
        return await generator.generate_all()
