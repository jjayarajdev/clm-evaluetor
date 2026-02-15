"""Event Detection Service - Scans contracts for actionable events.

This service scans contracts, SLAs, obligations, and key dates to detect
events that require action (notifications, approvals, external integrations).
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contract import Contract, ContractStatus
from app.models.event import Event, EventType, EventSeverity, EventStatus
from app.models.integration import SLAMeasurement
from app.models.key_date import ContractKeyDate, DateEventType
from app.models.obligation import Obligation, ObligationStatus
from app.models.sla import ContractSLA, SLAPerformance, BreachSeverity
from app.models.workflow import WorkflowDefinition

logger = logging.getLogger(__name__)


class EventDetector:
    """Detects contract events that require action.

    Scans various contract elements and creates Event records
    when actionable conditions are detected.
    """

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def run_full_scan(self) -> dict:
        """Run a complete scan for all event types.

        Returns:
            Summary of detected events by type.
        """
        logger.info("Starting full event detection scan")

        results = {
            "sla_breaches": 0,
            "sla_warnings": 0,
            "renewals_approaching": 0,
            "milestones_overdue": 0,
            "obligations_due": 0,
            "total_events": 0,
        }

        # Run all detection methods
        results["sla_breaches"] = await self.detect_sla_breaches()
        results["sla_warnings"] = await self.detect_sla_warnings()
        results["renewals_approaching"] = await self.detect_renewal_approaching()
        results["milestones_overdue"] = await self.detect_milestones_overdue()
        results["obligations_due"] = await self.detect_obligations_due()

        results["total_events"] = sum(results.values())

        logger.info(f"Event detection complete: {results['total_events']} events created")
        return results

    async def detect_sla_breaches(self) -> int:
        """Detect SLA breaches from recent measurements.

        Scans SLAMeasurement records where is_breach=True and no event
        has been generated yet.

        Returns:
            Number of breach events created.
        """
        logger.info("Scanning for SLA breaches")

        # Find breach measurements without events
        query = (
            select(SLAMeasurement)
            .where(
                and_(
                    SLAMeasurement.is_breach == True,
                    SLAMeasurement.event_generated == False,
                )
            )
            .options(selectinload(SLAMeasurement.sla))
        )

        result = await self.db.execute(query)
        breaches = result.scalars().all()

        events_created = 0
        for measurement in breaches:
            sla = measurement.sla
            if not sla:
                continue

            # Get contract info
            contract = await self._get_contract(sla.contract_id)
            if not contract:
                continue

            # Determine severity based on deviation
            severity = self._determine_severity(measurement.deviation_percent)

            # Create the event
            event = Event(
                event_type=EventType.sla_breach,
                severity=severity,
                contract_id=sla.contract_id,
                sla_id=sla.id,
                title=f"SLA Breach: {sla.sla_name}",
                description=self._build_breach_description(sla, measurement, contract),
                details={
                    "sla_name": sla.sla_name,
                    "metric_type": sla.metric_type.value,
                    "target_value": float(sla.target_value),
                    "actual_value": float(measurement.actual_value),
                    "deviation_percent": float(measurement.deviation_percent) if measurement.deviation_percent else 0,
                    "measurement_date": measurement.measurement_date.isoformat(),
                    "period_start": measurement.period_start.isoformat() if measurement.period_start else None,
                    "period_end": measurement.period_end.isoformat() if measurement.period_end else None,
                    "unit": sla.metric_unit.value,
                    "contract_name": contract.filename,
                    "counterparty": contract.counterparty,
                    "has_penalty": sla.has_penalty,
                    "penalty_value": float(sla.penalty_value) if sla.penalty_value else None,
                },
                detected_by="event_detector",
                status=EventStatus.pending,
            )

            # Link to default workflow for this event type
            workflow = await self._get_default_workflow(EventType.sla_breach)
            if workflow:
                event.workflow_id = workflow.id

            self.db.add(event)
            await self.db.flush()

            # Mark measurement as processed
            measurement.event_generated = True
            measurement.event_id = event.id

            events_created += 1
            logger.info(f"Created SLA breach event for {sla.sla_name} (deviation: {measurement.deviation_percent}%)")

        await self.db.commit()
        return events_created

    async def detect_sla_warnings(self) -> int:
        """Detect SLAs approaching breach threshold.

        Scans active SLAs where current performance is between
        warning threshold and target value.

        Returns:
            Number of warning events created.
        """
        logger.info("Scanning for SLA warnings")

        # Find SLAs with warning thresholds that are approaching breach
        query = (
            select(ContractSLA)
            .where(
                and_(
                    ContractSLA.is_active == True,
                    ContractSLA.warning_threshold.isnot(None),
                    ContractSLA.current_compliance_rate.isnot(None),
                )
            )
        )

        result = await self.db.execute(query)
        slas = result.scalars().all()

        events_created = 0
        for sla in slas:
            # Check if compliance is below warning but above breach
            compliance = float(sla.current_compliance_rate)
            warning = float(sla.warning_threshold)
            target = float(sla.target_value)

            # For uptime-style metrics (higher is better)
            if sla.target_operator in (">=", ">"):
                is_warning = warning <= compliance < target
            else:  # For error-rate style (lower is better)
                is_warning = target < compliance <= warning

            if not is_warning:
                continue

            # Check if we already have a recent warning event
            existing = await self._check_existing_event(
                sla.contract_id,
                EventType.sla_warning,
                sla_id=sla.id,
                hours=24  # Don't create duplicate within 24 hours
            )
            if existing:
                continue

            contract = await self._get_contract(sla.contract_id)
            if not contract:
                continue

            event = Event(
                event_type=EventType.sla_warning,
                severity=EventSeverity.warning,
                contract_id=sla.contract_id,
                sla_id=sla.id,
                title=f"SLA Warning: {sla.sla_name} approaching breach",
                description=f"The SLA '{sla.sla_name}' for {contract.counterparty} is approaching its breach threshold. "
                           f"Current: {compliance}{sla.metric_unit.value}, Warning: {warning}, Target: {target}",
                details={
                    "sla_name": sla.sla_name,
                    "current_value": compliance,
                    "warning_threshold": warning,
                    "target_value": target,
                    "unit": sla.metric_unit.value,
                    "contract_name": contract.filename,
                    "counterparty": contract.counterparty,
                },
                detected_by="event_detector",
                status=EventStatus.pending,
            )

            workflow = await self._get_default_workflow(EventType.sla_warning)
            if workflow:
                event.workflow_id = workflow.id

            self.db.add(event)
            events_created += 1
            logger.info(f"Created SLA warning event for {sla.sla_name}")

        await self.db.commit()
        return events_created

    async def detect_renewal_approaching(
        self,
        days_ahead: int = 90
    ) -> int:
        """Detect contracts approaching renewal/expiration.

        Args:
            days_ahead: Number of days ahead to scan for renewals.

        Returns:
            Number of renewal events created.
        """
        logger.info(f"Scanning for renewals in next {days_ahead} days")

        now = datetime.utcnow()
        cutoff = now + timedelta(days=days_ahead)

        # Find active contracts expiring within the window
        query = (
            select(Contract)
            .where(
                and_(
                    Contract.status == ContractStatus.active,
                    Contract.expiration_date.isnot(None),
                    Contract.expiration_date <= cutoff.date(),
                    Contract.expiration_date >= now.date(),
                )
            )
        )

        result = await self.db.execute(query)
        contracts = result.scalars().all()

        events_created = 0
        for contract in contracts:
            # Check for existing recent event
            existing = await self._check_existing_event(
                contract.id,
                EventType.renewal_approaching,
                hours=168  # 7 days
            )
            if existing:
                continue

            days_until = (contract.expiration_date - now.date()).days

            # Determine severity based on days remaining
            if days_until <= 14:
                severity = EventSeverity.critical
            elif days_until <= 30:
                severity = EventSeverity.warning
            else:
                severity = EventSeverity.info

            event = Event(
                event_type=EventType.renewal_approaching,
                severity=severity,
                contract_id=contract.id,
                title=f"Renewal Approaching: {contract.filename}",
                description=f"Contract with {contract.counterparty} expires in {days_until} days on {contract.expiration_date}. "
                           f"Review and take action if renewal is required.",
                details={
                    "contract_name": contract.filename,
                    "counterparty": contract.counterparty,
                    "expiration_date": contract.expiration_date.isoformat(),
                    "days_until_expiry": days_until,
                    "contract_value": float(contract.total_value) if contract.total_value else None,
                    "contract_type": contract.contract_type.value if contract.contract_type else None,
                },
                detected_by="event_detector",
                status=EventStatus.pending,
            )

            workflow = await self._get_default_workflow(EventType.renewal_approaching)
            if workflow:
                event.workflow_id = workflow.id

            self.db.add(event)
            events_created += 1
            logger.info(f"Created renewal event for {contract.filename} ({days_until} days)")

        await self.db.commit()
        return events_created

    async def detect_milestones_overdue(self) -> int:
        """Detect overdue contract milestones/key dates.

        Returns:
            Number of milestone overdue events created.
        """
        logger.info("Scanning for overdue milestones")

        now = datetime.utcnow()

        # Find overdue key dates that haven't been processed
        query = (
            select(ContractKeyDate)
            .where(
                and_(
                    ContractKeyDate.event_date < now.date(),
                    ContractKeyDate.is_completed == False,
                    or_(
                        ContractKeyDate.event_type == DateEventType.MILESTONE,
                        ContractKeyDate.event_type == DateEventType.DELIVERABLE,
                    )
                )
            )
        )

        result = await self.db.execute(query)
        key_dates = result.scalars().all()

        events_created = 0
        for key_date in key_dates:
            # Check for existing event
            existing = await self._check_existing_event(
                key_date.contract_id,
                EventType.milestone_overdue,
                hours=48
            )
            if existing:
                continue

            contract = await self._get_contract(key_date.contract_id)
            if not contract:
                continue

            days_overdue = (now.date() - key_date.event_date).days

            event = Event(
                event_type=EventType.milestone_overdue,
                severity=EventSeverity.warning if days_overdue < 7 else EventSeverity.critical,
                contract_id=key_date.contract_id,
                title=f"Milestone Overdue: {key_date.event_name}",
                description=f"The milestone '{key_date.event_name}' for {contract.counterparty} "
                           f"was due on {key_date.event_date} and is now {days_overdue} days overdue.",
                details={
                    "milestone_name": key_date.event_name,
                    "milestone_description": key_date.description,
                    "due_date": key_date.event_date.isoformat(),
                    "days_overdue": days_overdue,
                    "contract_name": contract.filename,
                    "counterparty": contract.counterparty,
                    "responsible_party": key_date.responsible_party,
                },
                detected_by="event_detector",
                status=EventStatus.pending,
            )

            workflow = await self._get_default_workflow(EventType.milestone_overdue)
            if workflow:
                event.workflow_id = workflow.id

            self.db.add(event)
            events_created += 1
            logger.info(f"Created milestone overdue event for {key_date.event_name}")

        await self.db.commit()
        return events_created

    async def detect_obligations_due(
        self,
        days_ahead: int = 7
    ) -> int:
        """Detect obligations coming due soon.

        Args:
            days_ahead: Days to look ahead for due obligations.

        Returns:
            Number of obligation due events created.
        """
        logger.info(f"Scanning for obligations due in {days_ahead} days")

        now = datetime.utcnow()
        cutoff = now + timedelta(days=days_ahead)

        # Find pending obligations coming due
        query = (
            select(Obligation)
            .where(
                and_(
                    Obligation.status == ObligationStatus.pending,
                    Obligation.deadline.isnot(None),
                    Obligation.deadline <= cutoff.date(),
                    Obligation.deadline >= now.date(),
                )
            )
        )

        result = await self.db.execute(query)
        obligations = result.scalars().all()

        events_created = 0
        for obligation in obligations:
            # Check for existing event
            existing = await self._check_existing_event(
                obligation.contract_id,
                EventType.obligation_due,
                hours=24
            )
            if existing:
                continue

            contract = await self._get_contract(obligation.contract_id)
            if not contract:
                continue

            days_remaining = (obligation.deadline - now.date()).days

            event = Event(
                event_type=EventType.obligation_due,
                severity=EventSeverity.warning if days_remaining > 2 else EventSeverity.critical,
                contract_id=obligation.contract_id,
                obligation_id=obligation.id,
                title=f"Obligation Due: {obligation.description[:50]}...",
                description=f"Obligation '{obligation.description}' is due in {days_remaining} days on {obligation.deadline}.",
                details={
                    "obligation_description": obligation.description,
                    "due_date": obligation.deadline.isoformat(),
                    "days_remaining": days_remaining,
                    "obligation_category": obligation.category.value if obligation.category else None,
                    "obligation_owner": obligation.owner.value if obligation.owner else None,
                    "contract_name": contract.filename,
                    "counterparty": contract.counterparty,
                },
                detected_by="event_detector",
                status=EventStatus.pending,
            )

            workflow = await self._get_default_workflow(EventType.obligation_due)
            if workflow:
                event.workflow_id = workflow.id

            self.db.add(event)
            events_created += 1
            logger.info(f"Created obligation due event for {obligation.description[:30]}...")

        await self.db.commit()
        return events_created

    # Helper methods

    async def _get_contract(self, contract_id: UUID) -> Optional[Contract]:
        """Fetch a contract by ID."""
        result = await self.db.execute(
            select(Contract).where(Contract.id == contract_id)
        )
        return result.scalar_one_or_none()

    async def _get_default_workflow(
        self,
        event_type: EventType
    ) -> Optional[WorkflowDefinition]:
        """Get the default workflow for an event type."""
        result = await self.db.execute(
            select(WorkflowDefinition)
            .where(
                and_(
                    WorkflowDefinition.event_type == event_type,
                    WorkflowDefinition.is_default == True,
                    WorkflowDefinition.is_active == True,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _check_existing_event(
        self,
        contract_id: UUID,
        event_type: EventType,
        hours: int = 24,
        sla_id: Optional[UUID] = None,
    ) -> bool:
        """Check if a similar event exists within the time window."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        conditions = [
            Event.contract_id == contract_id,
            Event.event_type == event_type,
            Event.detected_at >= cutoff,
        ]

        if sla_id:
            conditions.append(Event.sla_id == sla_id)

        result = await self.db.execute(
            select(Event).where(and_(*conditions)).limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _determine_severity(self, deviation_percent: Optional[float]) -> EventSeverity:
        """Determine event severity based on deviation percentage."""
        if deviation_percent is None:
            return EventSeverity.warning

        deviation = abs(deviation_percent)
        if deviation > 30:
            return EventSeverity.critical
        elif deviation > 15:
            return EventSeverity.warning
        else:
            return EventSeverity.info

    def _build_breach_description(
        self,
        sla: ContractSLA,
        measurement: SLAMeasurement,
        contract: Contract
    ) -> str:
        """Build a detailed breach description."""
        deviation = measurement.deviation_percent or 0

        desc = (
            f"SLA '{sla.sla_name}' for contract with {contract.counterparty} has been breached. "
            f"Target: {sla.target_value}{sla.metric_unit.value}, "
            f"Actual: {measurement.actual_value}{sla.metric_unit.value}, "
            f"Deviation: {abs(deviation):.1f}%. "
        )

        if sla.has_penalty and sla.penalty_value:
            desc += f"This breach may trigger a service credit of {sla.penalty_type}: {sla.penalty_value}. "

        if sla.consecutive_breaches > 0:
            desc += f"This is breach #{sla.consecutive_breaches + 1} for this SLA."

        return desc
