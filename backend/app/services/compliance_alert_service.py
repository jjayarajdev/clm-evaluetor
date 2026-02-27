"""Compliance Alert Service.

Creates and manages alerts for compliance-related issues:
- Missing compliance documents (CRITICAL/HIGH severity)
- Compliance document expiration
- Regulatory obligation deadlines
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance_gap import ComplianceGap
from app.models.contract import Contract
from app.models.industry import ComplianceGapSeverity
from app.models.regulatory_obligation import RegulatoryObligation
from app.models.sla_alert import (
    SLAAlert,
    AlertCategory,
    AlertPriority,
    AlertStatus,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


# Mapping from compliance gap severity to alert priority
GAP_SEVERITY_TO_PRIORITY = {
    ComplianceGapSeverity.CRITICAL: AlertPriority.CRITICAL,
    ComplianceGapSeverity.HIGH: AlertPriority.HIGH,
    ComplianceGapSeverity.MEDIUM: AlertPriority.MEDIUM,
    ComplianceGapSeverity.LOW: AlertPriority.LOW,
}


# Alert categories for compliance
# Using existing AlertCategory enum - extend with compliance categories
COMPLIANCE_GAP_CATEGORY = AlertCategory.OBLIGATION_DUE  # Reuse for now


class ComplianceAlertService:
    """Service for creating and managing compliance-related alerts."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._notification_service: Optional[NotificationService] = None

    @property
    def notification_service(self) -> NotificationService:
        """Lazy-load notification service."""
        if self._notification_service is None:
            self._notification_service = NotificationService(self.db)
        return self._notification_service

    async def create_missing_document_alert(
        self,
        contract_id: UUID,
        gap: ComplianceGap,
        source_system: str = "compliance_checker",
    ) -> SLAAlert:
        """Create an alert for a missing compliance document.

        Args:
            contract_id: Contract ID with the gap.
            gap: The compliance gap that triggered the alert.
            source_system: System that detected the gap.

        Returns:
            Created SLAAlert.
        """
        priority = GAP_SEVERITY_TO_PRIORITY.get(gap.severity, AlertPriority.MEDIUM)

        # Build alert title
        doc_type_name = gap.missing_document_type.value.replace("_", " ").title()
        title = f"COMPLIANCE GAP: Missing {doc_type_name}"

        # Build alert description
        description_parts = [gap.gap_description]
        if gap.regulatory_reference:
            description_parts.append(f"Regulatory requirement: {gap.regulatory_reference}")
        if gap.resolution_due_date:
            description_parts.append(f"Resolution due: {gap.resolution_due_date}")

        description = " ".join(description_parts)

        # Create alert
        alert = SLAAlert(
            contract_id=contract_id,
            category=COMPLIANCE_GAP_CATEGORY,
            priority=priority,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            detected_at=datetime.utcnow(),
            source_system=source_system,
            extra_data={
                "gap_id": str(gap.id),
                "missing_document_type": gap.missing_document_type.value,
                "severity": gap.severity.value,
                "regulatory_reference": gap.regulatory_reference,
                "alert_type": "compliance_gap",
            },
        )

        self.db.add(alert)
        await self.db.flush()

        logger.info(
            f"Created compliance gap alert for contract {contract_id}: "
            f"{doc_type_name} [{priority.value}]"
        )

        # Send notification if critical or high priority
        if priority in [AlertPriority.CRITICAL, AlertPriority.HIGH]:
            try:
                await self._send_compliance_notification(alert, gap)
            except Exception as e:
                logger.error(f"Failed to send compliance notification: {e}")

        return alert

    async def create_regulatory_deadline_alert(
        self,
        obligation: RegulatoryObligation,
        days_until_due: int,
        source_system: str = "regulatory_monitor",
    ) -> SLAAlert:
        """Create an alert for an upcoming regulatory deadline.

        Args:
            obligation: The regulatory obligation with upcoming deadline.
            days_until_due: Number of days until the obligation is due.
            source_system: System that detected the deadline.

        Returns:
            Created SLAAlert.
        """
        # Determine priority based on days until due
        if days_until_due <= 3:
            priority = AlertPriority.CRITICAL
        elif days_until_due <= 7:
            priority = AlertPriority.HIGH
        elif days_until_due <= 14:
            priority = AlertPriority.MEDIUM
        else:
            priority = AlertPriority.LOW

        # Build alert title
        title = f"REGULATORY DEADLINE: {obligation.title}"

        # Build alert description
        description_parts = [
            f"{obligation.description}",
            f"Due in {days_until_due} days ({obligation.next_due_date}).",
            f"Regulation: {obligation.regulation_type.value.upper()}",
        ]
        if obligation.regulation_reference:
            description_parts.append(f"Reference: {obligation.regulation_reference}")
        if obligation.responsible_party:
            description_parts.append(f"Responsible: {obligation.responsible_party}")

        description = " ".join(description_parts)

        # Create alert
        alert = SLAAlert(
            contract_id=obligation.contract_id,
            category=COMPLIANCE_GAP_CATEGORY,
            priority=priority,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            detected_at=datetime.utcnow(),
            source_system=source_system,
            extra_data={
                "obligation_id": str(obligation.id),
                "regulation_type": obligation.regulation_type.value,
                "obligation_category": obligation.obligation_category.value,
                "days_until_due": days_until_due,
                "alert_type": "regulatory_deadline",
            },
        )

        self.db.add(alert)
        await self.db.flush()

        logger.info(
            f"Created regulatory deadline alert for obligation {obligation.id}: "
            f"due in {days_until_due} days [{priority.value}]"
        )

        return alert

    async def create_compliance_document_expiring_alert(
        self,
        contract_id: UUID,
        document: Contract,
        days_until_expiry: int,
        source_system: str = "document_monitor",
    ) -> SLAAlert:
        """Create an alert for an expiring compliance document.

        Args:
            contract_id: Parent contract ID.
            document: The compliance document that is expiring.
            days_until_expiry: Days until the document expires.
            source_system: System that detected the expiry.

        Returns:
            Created SLAAlert.
        """
        # Determine priority based on days until expiry
        if days_until_expiry <= 7:
            priority = AlertPriority.CRITICAL
        elif days_until_expiry <= 30:
            priority = AlertPriority.HIGH
        elif days_until_expiry <= 60:
            priority = AlertPriority.MEDIUM
        else:
            priority = AlertPriority.LOW

        # Build alert title
        title = f"COMPLIANCE DOCUMENT EXPIRING: {document.filename}"

        # Build alert description
        description = (
            f"The compliance document '{document.filename}' linked to this contract "
            f"will expire in {days_until_expiry} days ({document.expiration_date}). "
            f"A renewal or replacement document may be required to maintain compliance."
        )

        # Create alert
        alert = SLAAlert(
            contract_id=contract_id,
            category=AlertCategory.CONTRACT_EXPIRY,
            priority=priority,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            detected_at=datetime.utcnow(),
            source_system=source_system,
            extra_data={
                "expiring_document_id": str(document.id),
                "days_until_expiry": days_until_expiry,
                "alert_type": "compliance_document_expiry",
            },
        )

        self.db.add(alert)
        await self.db.flush()

        logger.info(
            f"Created document expiry alert for {document.filename}: "
            f"expires in {days_until_expiry} days [{priority.value}]"
        )

        return alert

    async def check_and_create_regulatory_alerts(
        self,
        contract_id: UUID,
        days_threshold: int = 30,
    ) -> list[SLAAlert]:
        """Check regulatory obligations and create alerts for upcoming deadlines.

        Args:
            contract_id: Contract to check.
            days_threshold: Create alerts for obligations due within this many days.

        Returns:
            List of created alerts.
        """
        from datetime import date, timedelta

        # Find obligations due within threshold
        due_date_threshold = date.today() + timedelta(days=days_threshold)

        query = (
            select(RegulatoryObligation)
            .where(RegulatoryObligation.contract_id == contract_id)
            .where(RegulatoryObligation.next_due_date != None)
            .where(RegulatoryObligation.next_due_date <= due_date_threshold)
            .where(RegulatoryObligation.next_due_date >= date.today())
        )

        result = await self.db.execute(query)
        obligations = result.scalars().all()

        alerts = []
        for obl in obligations:
            days_until_due = (obl.next_due_date - date.today()).days
            alert = await self.create_regulatory_deadline_alert(obl, days_until_due)
            alerts.append(alert)

        return alerts

    async def _send_compliance_notification(
        self,
        alert: SLAAlert,
        gap: ComplianceGap,
    ) -> None:
        """Send notification for a compliance alert.

        Args:
            alert: The alert to notify about.
            gap: The compliance gap that triggered the alert.
        """
        # Get contract for context
        result = await self.db.execute(
            select(Contract).where(Contract.id == alert.contract_id)
        )
        contract = result.scalar_one_or_none()

        if not contract:
            logger.warning(f"Contract {alert.contract_id} not found for notification")
            return

        # Build notification context
        notification_data = {
            "alert_title": alert.title,
            "alert_description": alert.description,
            "contract_filename": contract.filename,
            "contract_counterparty": contract.counterparty,
            "gap_severity": gap.severity.value,
            "regulatory_reference": gap.regulatory_reference,
            "resolution_due_date": str(gap.resolution_due_date) if gap.resolution_due_date else None,
        }

        # Use notification service to send
        # This integrates with the existing notification infrastructure
        try:
            await self.notification_service.send_alert_notification(
                alert=alert,
                template_name="compliance_gap_alert",
                extra_data=notification_data,
            )
        except Exception as e:
            logger.error(f"Failed to send compliance notification: {e}")
            raise


async def create_compliance_alerts_for_gaps(
    db: AsyncSession,
    contract_id: UUID,
    gaps: list[ComplianceGap],
) -> list[SLAAlert]:
    """Create alerts for a list of compliance gaps.

    Only creates alerts for CRITICAL and HIGH severity gaps.

    Args:
        db: Database session.
        contract_id: Contract with the gaps.
        gaps: List of compliance gaps.

    Returns:
        List of created alerts.
    """
    service = ComplianceAlertService(db)
    alerts = []

    for gap in gaps:
        if gap.severity in [ComplianceGapSeverity.CRITICAL, ComplianceGapSeverity.HIGH]:
            alert = await service.create_missing_document_alert(contract_id, gap)
            alerts.append(alert)

    return alerts
