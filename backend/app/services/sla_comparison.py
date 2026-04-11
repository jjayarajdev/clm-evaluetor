"""SLA Comparison Engine.

Compares contracted SLA targets against actual performance values
from external systems (or stubs). Calculates breaches, service credits,
and earnback eligibility.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.servicenow_stub import get_servicenow_stub
from app.connectors.base import SLAActualValue
from app.models.sla import (
    BreachSeverity,
    ContractSLA,
    SLAPerformance,
    SLASeverity,
)
from app.services.sla_alert_service import SLAAlertService

logger = logging.getLogger(__name__)


class ComplianceStatus(str, Enum):
    """SLA compliance status."""

    COMPLIANT = "compliant"  # Meeting or exceeding target
    WARNING = "warning"  # Below target but above minimum
    BREACH = "breach"  # Below minimum threshold
    NO_DATA = "no_data"  # No actual data available


@dataclass
class SLAComparisonResult:
    """Result of comparing a single SLA."""

    sla_id: uuid.UUID
    sla_reference: str
    sla_name: str
    category: str | None

    # Contracted values
    target_value: Decimal
    minimum_value: Decimal | None
    target_operator: str

    # Actual values
    actual_value: Decimal | None
    measurement_period_start: date | None
    measurement_period_end: date | None

    # Comparison results
    status: ComplianceStatus
    deviation_from_target: Decimal | None  # Percentage
    deviation_from_minimum: Decimal | None  # Percentage
    breach_severity: BreachSeverity | None

    # Credits
    service_credit_applicable: bool = False
    service_credit_amount: Decimal | None = None
    at_risk_percentage: Decimal | None = None

    # Earnback
    earnback_eligible: bool = False
    consecutive_compliant_months: int = 0

    # Source
    source_system: str = ""
    notes: str | None = None


@dataclass
class ContractComparisonSummary:
    """Summary of all SLA comparisons for a contract."""

    contract_id: uuid.UUID
    measurement_period_start: date
    measurement_period_end: date
    generated_at: datetime = field(default_factory=datetime.utcnow)

    # Results
    sla_comparisons: list[SLAComparisonResult] = field(default_factory=list)

    # Summary statistics
    total_slas: int = 0
    compliant_count: int = 0
    warning_count: int = 0
    breach_count: int = 0
    no_data_count: int = 0

    # Financial
    total_at_risk: Decimal = Decimal("0")
    total_credits_due: Decimal = Decimal("0")
    potential_earnback: Decimal = Decimal("0")

    # Overall status
    overall_compliance_rate: Decimal = Decimal("0")
    overall_status: ComplianceStatus = ComplianceStatus.NO_DATA


class SLAComparisonEngine:
    """Engine for comparing contracted SLAs against actual performance."""

    # Breach severity thresholds (deviation from minimum)
    BREACH_THRESHOLDS = {
        BreachSeverity.MINOR: Decimal("5"),  # <5% below minimum
        BreachSeverity.MODERATE: Decimal("15"),  # 5-15% below
        BreachSeverity.MAJOR: Decimal("30"),  # 15-30% below
        BreachSeverity.CRITICAL: Decimal("100"),  # >30% below
    }

    # Service credit calculation (percentage of at-risk pool)
    CREDIT_RATES = {
        BreachSeverity.MINOR: Decimal("0.25"),  # 25% of at-risk
        BreachSeverity.MODERATE: Decimal("0.50"),  # 50% of at-risk
        BreachSeverity.MAJOR: Decimal("0.75"),  # 75% of at-risk
        BreachSeverity.CRITICAL: Decimal("1.00"),  # 100% of at-risk
    }

    # Map common SLA name patterns to known section references for demo
    SLA_NAME_TO_REFERENCE = {
        "uptime": "2.1.1",
        "availability": "2.1.1",
        "laptop": "2.1.2",
        "desktop": "2.1.1",
        "network": "2.2.1",
        "service desk": "12.4.1",
        "call": "12.3.1",
        "abandonment": "12.3.2",
        "incident": "12.4.1",
        "resolution": "12.4.1",
        "contact": "12.1.1",
        "authorisation": "12.2.1",
        "authorization": "12.2.1",
        "response": "12.1",
        "catalog": "11.1",
        "software": "11.2",
        "hardware": "11.1",
    }

    def __init__(self, db: AsyncSession, create_alerts: bool = True):
        self.db = db
        self._connector = get_servicenow_stub()
        self._create_alerts = create_alerts
        self._alert_service: SLAAlertService | None = None

    def _infer_section_reference(self, sla_name: str) -> str | None:
        """Infer a section reference from SLA name for demo purposes.

        Args:
            sla_name: The SLA name to analyze.

        Returns:
            A section reference if a match is found, None otherwise.
        """
        name_lower = sla_name.lower()
        for pattern, ref in self.SLA_NAME_TO_REFERENCE.items():
            if pattern in name_lower:
                return ref
        return None

    @property
    def alert_service(self) -> SLAAlertService:
        """Lazy-load alert service."""
        if self._alert_service is None:
            self._alert_service = SLAAlertService(self.db)
        return self._alert_service

    async def compare_contract_slas(
        self,
        contract_id: uuid.UUID,
        start_date: date,
        end_date: date,
        store_results: bool = True,
    ) -> ContractComparisonSummary:
        """Compare all SLAs for a contract against actual values.

        Args:
            contract_id: Contract to compare.
            start_date: Start of measurement period.
            end_date: End of measurement period.
            store_results: Whether to store results in database.

        Returns:
            ContractComparisonSummary with all comparisons.
        """
        summary = ContractComparisonSummary(
            contract_id=contract_id,
            measurement_period_start=start_date,
            measurement_period_end=end_date,
        )

        # Fetch contracted SLAs
        result = await self.db.execute(
            select(ContractSLA)
            .where(ContractSLA.contract_id == contract_id)
            .where(ContractSLA.is_active == True)
        )
        slas = result.scalars().all()

        if not slas:
            logger.warning(f"No active SLAs found for contract {contract_id}")
            return summary

        # Get SLA references for connector query
        # Each SLA gets a unique ref key to ensure separate stub values
        sla_refs = []
        sla_ref_map: dict[uuid.UUID, str] = {}  # Map SLA ID to unique reference key
        contracted_slas: dict[str, dict] = {}  # Pass target info to stub for scale-aware generation
        used_refs: set[str] = set()  # Track all used refs to guarantee uniqueness
        for s in slas:
            base_ref = s.section_reference
            if not base_ref:
                base_ref = self._infer_section_reference(s.sla_name)
            if not base_ref:
                base_ref = s.sla_name.lower().replace(" ", "_")[:30]
            # Ensure uniqueness across all generated refs
            ref = base_ref
            if ref in used_refs:
                # Use full SLA name for disambiguation
                name_slug = s.sla_name.lower().replace(" ", "_").replace("-", "_")
                ref = f"{base_ref}::{name_slug}"
                # If still colliding, append a counter
                counter = 2
                while ref in used_refs:
                    ref = f"{base_ref}::{name_slug}_{counter}"
                    counter += 1
            used_refs.add(ref)
            sla_refs.append(ref)
            sla_ref_map[s.id] = ref
            contracted_slas[ref] = {
                "target_value": float(s.target_value) if s.target_value else 0.95,
                "minimum_value": float(s.minimum_service_level or s.warning_threshold or 0),
                "operator": s.target_operator or ">=",
            }

        # Fetch actual values from connector
        await self._connector.connect()
        actuals_result = await self._connector.get_sla_actuals(
            list(set(sla_refs)), start_date, end_date,
            contracted_slas=contracted_slas,
        )

        # Build lookup map for actuals
        actuals_map: dict[str, SLAActualValue] = {}
        if actuals_result.success and actuals_result.data:
            actuals_map = {a.sla_reference: a for a in actuals_result.data}

        # Compare each SLA
        for sla in slas:
            # Use effective reference (may be inferred)
            effective_ref = sla_ref_map.get(sla.id)
            actual = actuals_map.get(effective_ref) if effective_ref else None
            comparison = self._compare_sla(sla, actual)
            summary.sla_comparisons.append(comparison)

            # Update counts
            summary.total_slas += 1
            if comparison.status == ComplianceStatus.COMPLIANT:
                summary.compliant_count += 1
            elif comparison.status == ComplianceStatus.WARNING:
                summary.warning_count += 1
            elif comparison.status == ComplianceStatus.BREACH:
                summary.breach_count += 1
            else:
                summary.no_data_count += 1

            # Accumulate financial totals
            if sla.at_risk_percentage:
                summary.total_at_risk += sla.at_risk_percentage

            if comparison.service_credit_applicable and comparison.service_credit_amount:
                summary.total_credits_due += comparison.service_credit_amount

            if comparison.earnback_eligible and sla.at_risk_percentage:
                summary.potential_earnback += sla.at_risk_percentage * Decimal("0.5")

        # Calculate overall compliance rate
        if summary.total_slas > 0:
            compliant_with_warning = summary.compliant_count + summary.warning_count
            summary.overall_compliance_rate = (
                Decimal(compliant_with_warning) / Decimal(summary.total_slas) * 100
            ).quantize(Decimal("0.01"))

            # Determine overall status
            if summary.breach_count > 0:
                summary.overall_status = ComplianceStatus.BREACH
            elif summary.warning_count > 0:
                summary.overall_status = ComplianceStatus.WARNING
            elif summary.compliant_count > 0:
                summary.overall_status = ComplianceStatus.COMPLIANT

        # Store results if requested
        if store_results:
            await self._store_comparison_results(summary)

        # Create alerts for breaches and warnings
        if self._create_alerts:
            await self._create_alerts_from_comparison(summary)

        logger.info(
            f"SLA comparison complete for contract {contract_id}: "
            f"{summary.compliant_count}/{summary.total_slas} compliant, "
            f"{summary.breach_count} breaches, "
            f"credits due: {summary.total_credits_due}"
        )

        return summary

    def _compare_sla(
        self,
        sla: ContractSLA,
        actual: SLAActualValue | None,
    ) -> SLAComparisonResult:
        """Compare a single SLA against its actual value.

        Args:
            sla: Contracted SLA from database.
            actual: Actual value from connector (or None).

        Returns:
            SLAComparisonResult with comparison details.
        """
        result = SLAComparisonResult(
            sla_id=sla.id,
            sla_reference=sla.section_reference or "",
            sla_name=sla.sla_name,
            category=sla.category,
            target_value=sla.target_value,
            minimum_value=sla.minimum_service_level or sla.warning_threshold,
            target_operator=sla.target_operator,
            actual_value=None,
            measurement_period_start=None,
            measurement_period_end=None,
            status=ComplianceStatus.NO_DATA,
            deviation_from_target=None,
            deviation_from_minimum=None,
            breach_severity=None,
            at_risk_percentage=sla.at_risk_percentage,
            earnback_eligible=sla.earnback_eligible,
            source_system="",
        )

        if actual is None:
            result.notes = "No actual data available from external system."
            return result

        # Set actual values
        result.actual_value = actual.actual_value
        result.measurement_period_start = actual.measurement_period_start
        result.measurement_period_end = actual.measurement_period_end
        result.source_system = actual.source_system

        # Calculate deviations
        # Note: stub connector now generates scale-aware values (same unit as target),
        # so no normalization needed here.
        target = sla.target_value
        minimum = sla.minimum_service_level or sla.warning_threshold or target * Decimal("0.9")
        actual_val = actual.actual_value

        # Deviation from target (percentage)
        if target and target != 0:
            result.deviation_from_target = (
                (actual_val - target) / target * 100
            ).quantize(Decimal("0.01"))

        # Deviation from minimum (percentage)
        if minimum and minimum != 0:
            result.deviation_from_minimum = (
                (actual_val - minimum) / minimum * 100
            ).quantize(Decimal("0.01"))

        # Determine compliance status based on operator
        operator = sla.target_operator
        is_compliant_with_target = self._check_compliance(actual_val, target, operator)
        is_compliant_with_minimum = self._check_compliance(actual_val, minimum, operator)

        if is_compliant_with_target:
            result.status = ComplianceStatus.COMPLIANT
            result.notes = "Performance meets or exceeds target."
        elif is_compliant_with_minimum:
            result.status = ComplianceStatus.WARNING
            result.notes = f"Performance below target by {abs(result.deviation_from_target or 0):.1f}% but above minimum."
        else:
            result.status = ComplianceStatus.BREACH
            result.breach_severity = self._determine_breach_severity(result.deviation_from_minimum)
            result.notes = f"BREACH: Performance {abs(result.deviation_from_minimum or 0):.1f}% below minimum threshold."

            # Calculate service credit
            if sla.has_penalty and sla.at_risk_percentage:
                result.service_credit_applicable = True
                credit_rate = self.CREDIT_RATES.get(result.breach_severity, Decimal("0.25"))
                result.service_credit_amount = (sla.at_risk_percentage * credit_rate).quantize(Decimal("0.01"))
                result.notes += f" Service credit: {result.service_credit_amount}% of at-risk pool."

        # Check earnback eligibility (compliant after previous breach)
        if sla.earnback_eligible and result.status == ComplianceStatus.COMPLIANT:
            if sla.consecutive_breaches > 0:
                result.notes += " Earnback opportunity: Previous breach can be recovered."

        return result

    def _check_compliance(
        self,
        actual: Decimal,
        threshold: Decimal,
        operator: str,
    ) -> bool:
        """Check if actual value meets threshold based on operator.

        Args:
            actual: Actual value.
            threshold: Target or minimum threshold.
            operator: Comparison operator (>=, <=, =, >, <).

        Returns:
            True if compliant.
        """
        if operator == ">=":
            return actual >= threshold
        elif operator == "<=":
            return actual <= threshold
        elif operator == ">":
            return actual > threshold
        elif operator == "<":
            return actual < threshold
        elif operator == "=":
            # For equality, allow 1% tolerance
            tolerance = threshold * Decimal("0.01")
            return abs(actual - threshold) <= tolerance
        else:
            # Default to >=
            return actual >= threshold

    def _determine_breach_severity(self, deviation: Decimal | None) -> BreachSeverity:
        """Determine breach severity based on deviation from minimum.

        Args:
            deviation: Percentage deviation from minimum (negative for breach).

        Returns:
            BreachSeverity level.
        """
        if deviation is None:
            return BreachSeverity.MINOR

        abs_deviation = abs(deviation)

        if abs_deviation < 5:
            return BreachSeverity.MINOR
        elif abs_deviation < 15:
            return BreachSeverity.MODERATE
        elif abs_deviation < 30:
            return BreachSeverity.MAJOR
        else:
            return BreachSeverity.CRITICAL

    async def _store_comparison_results(self, summary: ContractComparisonSummary) -> None:
        """Store comparison results in database.

        Args:
            summary: Comparison summary to store.
        """
        for comparison in summary.sla_comparisons:
            if comparison.actual_value is None:
                continue

            # Create SLAPerformance record
            performance = SLAPerformance(
                sla_id=comparison.sla_id,
                actual_value=comparison.actual_value,
                measured_at=datetime.utcnow(),
                measurement_period_start=comparison.measurement_period_start,
                measurement_period_end=comparison.measurement_period_end,
                is_compliant=comparison.status != ComplianceStatus.BREACH,
                deviation_percentage=comparison.deviation_from_target,
                breach_severity=comparison.breach_severity,
                penalty_applied=comparison.service_credit_applicable,
                penalty_amount=None,  # Calculated separately
                credit_issued=comparison.service_credit_amount,
                notes=comparison.notes,
                recorded_by="comparison_engine",
            )
            self.db.add(performance)

            # Update SLA with latest compliance info
            await self.db.execute(
                update(ContractSLA)
                .where(ContractSLA.id == comparison.sla_id)
                .values(
                    current_compliance_rate=Decimal("100") if comparison.status == ComplianceStatus.COMPLIANT else Decimal("0"),
                    last_measured_at=datetime.utcnow(),
                    consecutive_breaches=(
                        ContractSLA.consecutive_breaches + 1
                        if comparison.status == ComplianceStatus.BREACH
                        else 0
                    ),
                )
            )

        await self.db.flush()

    async def _create_alerts_from_comparison(self, summary: ContractComparisonSummary) -> int:
        """Create alerts from comparison results.

        Args:
            summary: Comparison summary with results.

        Returns:
            Number of alerts created.
        """
        alerts_created = 0

        for comparison in summary.sla_comparisons:
            if comparison.status == ComplianceStatus.NO_DATA:
                continue

            if comparison.status == ComplianceStatus.BREACH:
                # Create breach alert
                await self.alert_service.create_breach_alert(
                    contract_id=summary.contract_id,
                    sla_id=comparison.sla_id,
                    sla_reference=comparison.sla_reference,
                    sla_name=comparison.sla_name,
                    target_value=comparison.target_value,
                    minimum_value=comparison.minimum_value,
                    actual_value=comparison.actual_value,
                    deviation_percentage=comparison.deviation_from_minimum or Decimal("0"),
                    breach_severity=comparison.breach_severity or BreachSeverity.MINOR,
                    measurement_start=datetime.combine(
                        comparison.measurement_period_start,
                        datetime.min.time()
                    ) if comparison.measurement_period_start else None,
                    measurement_end=datetime.combine(
                        comparison.measurement_period_end,
                        datetime.max.time()
                    ) if comparison.measurement_period_end else None,
                    source_system=comparison.source_system,
                    service_credit=comparison.service_credit_amount,
                    at_risk_amount=comparison.at_risk_percentage,
                    notes=comparison.notes,
                )
                alerts_created += 1

                # Also create service credit alert if applicable
                if comparison.service_credit_applicable and comparison.service_credit_amount:
                    await self.alert_service.create_service_credit_alert(
                        contract_id=summary.contract_id,
                        sla_id=comparison.sla_id,
                        sla_reference=comparison.sla_reference,
                        sla_name=comparison.sla_name,
                        credit_amount=comparison.service_credit_amount,
                        at_risk_percentage=comparison.at_risk_percentage or Decimal("0"),
                        breach_severity=comparison.breach_severity or BreachSeverity.MINOR,
                    )
                    alerts_created += 1

            elif comparison.status == ComplianceStatus.WARNING:
                # Create warning alert
                await self.alert_service.create_warning_alert(
                    contract_id=summary.contract_id,
                    sla_id=comparison.sla_id,
                    sla_reference=comparison.sla_reference,
                    sla_name=comparison.sla_name,
                    target_value=comparison.target_value,
                    minimum_value=comparison.minimum_value,
                    actual_value=comparison.actual_value,
                    deviation_percentage=comparison.deviation_from_target or Decimal("0"),
                    measurement_start=datetime.combine(
                        comparison.measurement_period_start,
                        datetime.min.time()
                    ) if comparison.measurement_period_start else None,
                    measurement_end=datetime.combine(
                        comparison.measurement_period_end,
                        datetime.max.time()
                    ) if comparison.measurement_period_end else None,
                    source_system=comparison.source_system,
                )
                alerts_created += 1

        logger.info(f"Created {alerts_created} alerts from SLA comparison")
        return alerts_created


async def run_sla_comparison(
    db: AsyncSession,
    contract_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ContractComparisonSummary:
    """Run SLA comparison for a contract.

    Convenience function for running comparison.

    Args:
        db: Database session.
        contract_id: Contract ID.
        start_date: Start date (default: start of current month).
        end_date: End date (default: today).

    Returns:
        Comparison summary.
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date.replace(day=1)

    engine = SLAComparisonEngine(db)
    return await engine.compare_contract_slas(contract_id, start_date, end_date)
