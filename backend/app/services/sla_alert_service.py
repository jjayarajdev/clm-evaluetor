"""SLA Alert Service - Triggers and manages alerts from SLA comparisons.

Integrates with the SLA comparison engine to generate alerts when:
- SLA breaches are detected (below minimum threshold)
- SLA warnings occur (below target but above minimum)
- Service credits are due
- Milestone delays are identified
- FX thresholds for COLA are triggered
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.sla import ContractSLA, BreachSeverity
from app.models.sla_alert import (
    SLAAlert,
    AlertCategory,
    AlertPriority,
    AlertStatus,
    BREACH_SEVERITY_TO_PRIORITY,
)
from app.models.notification import NotificationStatus
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class SLAAlertService:
    """Service for creating and managing SLA alerts."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._notification_service: Optional[NotificationService] = None

    @property
    def notification_service(self) -> NotificationService:
        """Lazy-load notification service."""
        if self._notification_service is None:
            self._notification_service = NotificationService(self.db)
        return self._notification_service

    async def create_breach_alert(
        self,
        contract_id: UUID,
        sla_id: UUID,
        sla_reference: str,
        sla_name: str,
        target_value: Decimal,
        minimum_value: Optional[Decimal],
        actual_value: Decimal,
        deviation_percentage: Decimal,
        breach_severity: BreachSeverity,
        measurement_start: Optional[datetime] = None,
        measurement_end: Optional[datetime] = None,
        source_system: str = "",
        service_credit: Optional[Decimal] = None,
        at_risk_amount: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> SLAAlert:
        """Create an alert for an SLA breach.

        Args:
            contract_id: Contract ID.
            sla_id: SLA ID.
            sla_reference: SLA section reference (e.g., "12.2.1").
            sla_name: Name of the SLA metric.
            target_value: Contracted target value.
            minimum_value: Minimum acceptable value.
            actual_value: Actual measured value.
            deviation_percentage: Percentage deviation from minimum.
            breach_severity: Severity level of breach.
            measurement_start: Start of measurement period.
            measurement_end: End of measurement period.
            source_system: Source of actual data.
            service_credit: Calculated service credit amount.
            at_risk_amount: Amount at risk.
            notes: Additional notes.

        Returns:
            Created SLAAlert.
        """
        # Determine priority from breach severity
        priority = BREACH_SEVERITY_TO_PRIORITY.get(
            breach_severity, AlertPriority.MEDIUM
        )

        # Build title and description
        title = f"SLA BREACH: {sla_name} ({sla_reference})"
        description = (
            f"Performance of {actual_value}% is {abs(deviation_percentage):.1f}% below "
            f"the minimum threshold of {minimum_value or target_value}%.\n\n"
            f"Target: {target_value}%\n"
            f"Minimum: {minimum_value or 'N/A'}\n"
            f"Actual: {actual_value}%\n"
            f"Breach Severity: {breach_severity.value.upper()}"
        )

        if service_credit:
            description += f"\n\nService Credit Due: {service_credit}%"

        if notes:
            description += f"\n\n{notes}"

        alert = SLAAlert(
            contract_id=contract_id,
            sla_id=sla_id,
            category=AlertCategory.SLA_BREACH,
            priority=priority,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            sla_reference=sla_reference,
            sla_name=sla_name,
            target_value=target_value,
            minimum_value=minimum_value,
            actual_value=actual_value,
            deviation_percentage=deviation_percentage,
            breach_severity=breach_severity,
            has_financial_impact=service_credit is not None and service_credit > 0,
            estimated_credit=service_credit,
            at_risk_amount=at_risk_amount,
            measurement_start=measurement_start,
            measurement_end=measurement_end,
            source_system=source_system,
        )

        self.db.add(alert)
        await self.db.flush()

        logger.warning(
            f"SLA breach alert created: {sla_name} - {breach_severity.value} severity"
        )

        return alert

    async def create_warning_alert(
        self,
        contract_id: UUID,
        sla_id: UUID,
        sla_reference: str,
        sla_name: str,
        target_value: Decimal,
        minimum_value: Optional[Decimal],
        actual_value: Decimal,
        deviation_percentage: Decimal,
        measurement_start: Optional[datetime] = None,
        measurement_end: Optional[datetime] = None,
        source_system: str = "",
    ) -> SLAAlert:
        """Create an alert for SLA warning (below target but above minimum).

        Args:
            contract_id: Contract ID.
            sla_id: SLA ID.
            sla_reference: SLA section reference.
            sla_name: Name of the SLA metric.
            target_value: Contracted target value.
            minimum_value: Minimum acceptable value.
            actual_value: Actual measured value.
            deviation_percentage: Percentage deviation from target.
            measurement_start: Start of measurement period.
            measurement_end: End of measurement period.
            source_system: Source of actual data.

        Returns:
            Created SLAAlert.
        """
        title = f"SLA WARNING: {sla_name} ({sla_reference})"
        description = (
            f"Performance of {actual_value}% is {abs(deviation_percentage):.1f}% below target "
            f"but still above minimum threshold.\n\n"
            f"Target: {target_value}%\n"
            f"Minimum: {minimum_value or 'N/A'}\n"
            f"Actual: {actual_value}%\n\n"
            f"Action recommended to prevent potential breach."
        )

        alert = SLAAlert(
            contract_id=contract_id,
            sla_id=sla_id,
            category=AlertCategory.SLA_WARNING,
            priority=AlertPriority.LOW,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            sla_reference=sla_reference,
            sla_name=sla_name,
            target_value=target_value,
            minimum_value=minimum_value,
            actual_value=actual_value,
            deviation_percentage=deviation_percentage,
            has_financial_impact=False,
            measurement_start=measurement_start,
            measurement_end=measurement_end,
            source_system=source_system,
        )

        self.db.add(alert)
        await self.db.flush()

        logger.info(f"SLA warning alert created: {sla_name}")

        return alert

    async def create_service_credit_alert(
        self,
        contract_id: UUID,
        sla_id: UUID,
        sla_reference: str,
        sla_name: str,
        credit_amount: Decimal,
        at_risk_percentage: Decimal,
        breach_severity: BreachSeverity,
    ) -> SLAAlert:
        """Create an alert for service credit due.

        Args:
            contract_id: Contract ID.
            sla_id: SLA ID.
            sla_reference: SLA section reference.
            sla_name: Name of the SLA metric.
            credit_amount: Calculated credit amount.
            at_risk_percentage: Percentage of at-risk pool.
            breach_severity: Severity of the breach.

        Returns:
            Created SLAAlert.
        """
        title = f"SERVICE CREDIT DUE: {sla_name} ({sla_reference})"
        description = (
            f"A service credit of {credit_amount}% is due based on a "
            f"{breach_severity.value.upper()} breach.\n\n"
            f"At-Risk Pool: {at_risk_percentage}%\n"
            f"Credit Rate: {(credit_amount / at_risk_percentage * 100) if at_risk_percentage else 0:.0f}%\n"
            f"Credit Due: {credit_amount}%\n\n"
            f"This credit should be applied to the next invoice."
        )

        alert = SLAAlert(
            contract_id=contract_id,
            sla_id=sla_id,
            category=AlertCategory.SERVICE_CREDIT,
            priority=AlertPriority.MEDIUM,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            sla_reference=sla_reference,
            sla_name=sla_name,
            breach_severity=breach_severity,
            has_financial_impact=True,
            estimated_credit=credit_amount,
            at_risk_amount=at_risk_percentage,
        )

        self.db.add(alert)
        await self.db.flush()

        return alert

    async def create_milestone_alert(
        self,
        contract_id: UUID,
        milestone_id: str,
        milestone_name: str,
        planned_date: datetime,
        status: str,  # "delayed" or "at_risk"
        days_variance: int,
        credit_at_risk: Optional[Decimal] = None,
        completion_percentage: int = 0,
        notes: Optional[str] = None,
    ) -> SLAAlert:
        """Create an alert for milestone delay or risk.

        Args:
            contract_id: Contract ID.
            milestone_id: Milestone identifier.
            milestone_name: Name of the milestone.
            planned_date: Planned completion date.
            status: "delayed" or "at_risk".
            days_variance: Days behind (positive = late).
            credit_at_risk: Credit amount at risk for this milestone.
            completion_percentage: Current completion percentage.
            notes: Additional notes.

        Returns:
            Created SLAAlert.
        """
        category = AlertCategory.MILESTONE_DELAYED if status == "delayed" else AlertCategory.MILESTONE_AT_RISK
        priority = AlertPriority.HIGH if status == "delayed" else AlertPriority.MEDIUM

        title = f"MILESTONE {'DELAYED' if status == 'delayed' else 'AT RISK'}: {milestone_name}"
        description = (
            f"Milestone {milestone_id} is {days_variance} days "
            f"{'behind schedule' if status == 'delayed' else 'at risk of delay'}.\n\n"
            f"Planned Date: {planned_date.strftime('%Y-%m-%d')}\n"
            f"Completion: {completion_percentage}%\n"
        )

        if credit_at_risk:
            description += f"Credit at Risk: ${credit_at_risk:,.2f}\n"

        if notes:
            description += f"\n{notes}"

        alert = SLAAlert(
            contract_id=contract_id,
            category=category,
            priority=priority,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            sla_reference=milestone_id,
            sla_name=milestone_name,
            has_financial_impact=credit_at_risk is not None and credit_at_risk > 0,
            at_risk_amount=credit_at_risk,
            extra_data={
                "milestone_id": milestone_id,
                "planned_date": planned_date.isoformat(),
                "days_variance": days_variance,
                "completion_percentage": completion_percentage,
            },
        )

        self.db.add(alert)
        await self.db.flush()

        return alert

    async def create_fx_threshold_alert(
        self,
        contract_id: UUID,
        base_currency: str,
        target_currency: str,
        contract_rate: Decimal,
        current_rate: Decimal,
        change_percentage: Decimal,
        threshold: Decimal,
        direction: str,  # "increase" or "decrease"
    ) -> SLAAlert:
        """Create an alert for FX rate threshold breach (COLA adjustment).

        Args:
            contract_id: Contract ID.
            base_currency: Base currency code.
            target_currency: Target currency code.
            contract_rate: Rate at contract signing.
            current_rate: Current exchange rate.
            change_percentage: Percentage change.
            threshold: Threshold that was breached.
            direction: Direction of change.

        Returns:
            Created SLAAlert.
        """
        title = f"FX ADJUSTMENT REQUIRED: {base_currency}/{target_currency}"
        description = (
            f"Exchange rate movement of {abs(change_percentage):.1f}% exceeds the "
            f"{threshold}% COLA threshold.\n\n"
            f"Contract Rate: {contract_rate:.4f}\n"
            f"Current Rate: {current_rate:.4f}\n"
            f"Change: {change_percentage:+.2f}%\n"
            f"Direction: {direction.upper()}\n\n"
            f"A price adjustment is applicable per contract terms."
        )

        alert = SLAAlert(
            contract_id=contract_id,
            category=AlertCategory.FX_THRESHOLD,
            priority=AlertPriority.MEDIUM,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            has_financial_impact=True,
            extra_data={
                "base_currency": base_currency,
                "target_currency": target_currency,
                "contract_rate": float(contract_rate),
                "current_rate": float(current_rate),
                "change_percentage": float(change_percentage),
                "threshold": float(threshold),
                "direction": direction,
            },
        )

        self.db.add(alert)
        await self.db.flush()

        return alert

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        user_id: UUID,
    ) -> SLAAlert:
        """Mark an alert as acknowledged.

        Args:
            alert_id: Alert ID.
            user_id: User acknowledging the alert.

        Returns:
            Updated SLAAlert.
        """
        result = await self.db.execute(
            select(SLAAlert).where(SLAAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id

        await self.db.flush()
        return alert

    async def resolve_alert(
        self,
        alert_id: UUID,
        user_id: UUID,
        resolution_notes: Optional[str] = None,
    ) -> SLAAlert:
        """Mark an alert as resolved.

        Args:
            alert_id: Alert ID.
            user_id: User resolving the alert.
            resolution_notes: Notes on how it was resolved.

        Returns:
            Updated SLAAlert.
        """
        result = await self.db.execute(
            select(SLAAlert).where(SLAAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user_id
        alert.resolution_notes = resolution_notes

        await self.db.flush()
        return alert

    async def escalate_alert(
        self,
        alert_id: UUID,
        escalate_to: str,
        notify: bool = True,
    ) -> SLAAlert:
        """Escalate an alert to a higher authority.

        Args:
            alert_id: Alert ID.
            escalate_to: Email or name of escalation contact.
            notify: Whether to send notification.

        Returns:
            Updated SLAAlert.
        """
        result = await self.db.execute(
            select(SLAAlert).where(SLAAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.ESCALATED
        alert.escalation_level += 1
        alert.escalated_at = datetime.utcnow()
        alert.escalated_to = escalate_to

        # Increase priority if not already critical
        if alert.priority != AlertPriority.CRITICAL:
            priorities = list(AlertPriority)
            current_idx = priorities.index(alert.priority)
            if current_idx < len(priorities) - 1:
                alert.priority = priorities[current_idx + 1]

        await self.db.flush()

        # Send escalation notification
        if notify and "@" in escalate_to:
            await self._send_escalation_notification(alert, escalate_to)

        return alert

    async def get_active_alerts(
        self,
        contract_id: Optional[UUID] = None,
        category: Optional[AlertCategory] = None,
        priority: Optional[AlertPriority] = None,
        limit: int = 100,
    ) -> list[SLAAlert]:
        """Get active alerts with optional filters.

        Args:
            contract_id: Filter by contract.
            category: Filter by category.
            priority: Filter by priority.
            limit: Maximum number to return.

        Returns:
            List of SLAAlert.
        """
        query = select(SLAAlert).where(
            SLAAlert.status.in_([
                AlertStatus.ACTIVE,
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.IN_PROGRESS,
            ])
        )

        if contract_id:
            query = query.where(SLAAlert.contract_id == contract_id)
        if category:
            query = query.where(SLAAlert.category == category)
        if priority:
            query = query.where(SLAAlert.priority == priority)

        query = query.order_by(
            SLAAlert.priority.desc(),
            SLAAlert.detected_at.desc()
        ).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_alert_summary(
        self,
        contract_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
    ) -> dict:
        """Get summary of alerts.

        Args:
            contract_id: Filter by contract (optional).
            tenant_id: Filter by tenant (optional).

        Returns:
            Dictionary with alert counts by status and priority.
        """
        from sqlalchemy import func

        def apply_filters(query):
            """Apply contract and tenant filters."""
            if contract_id:
                query = query.where(SLAAlert.contract_id == contract_id)
            if tenant_id:
                query = query.join(Contract, SLAAlert.contract_id == Contract.id).where(
                    Contract.tenant_id == tenant_id
                )
            return query

        # Count by status
        status_counts = {}
        for status in AlertStatus:
            query = select(func.count(SLAAlert.id)).where(SLAAlert.status == status)
            query = apply_filters(query)
            result = await self.db.execute(query)
            status_counts[status.value] = result.scalar() or 0

        # Count by priority (active only)
        priority_counts = {}
        for priority in AlertPriority:
            query = select(func.count(SLAAlert.id)).where(
                SLAAlert.priority == priority,
                SLAAlert.status.in_([
                    AlertStatus.ACTIVE,
                    AlertStatus.ACKNOWLEDGED,
                    AlertStatus.IN_PROGRESS,
                ])
            )
            query = apply_filters(query)
            result = await self.db.execute(query)
            priority_counts[priority.value] = result.scalar() or 0

        # Count by category (active only)
        category_counts = {}
        for category in AlertCategory:
            query = select(func.count(SLAAlert.id)).where(
                SLAAlert.category == category,
                SLAAlert.status.in_([
                    AlertStatus.ACTIVE,
                    AlertStatus.ACKNOWLEDGED,
                    AlertStatus.IN_PROGRESS,
                ])
            )
            query = apply_filters(query)
            result = await self.db.execute(query)
            category_counts[category.value] = result.scalar() or 0

        # Calculate totals
        active_count = sum(
            status_counts.get(s.value, 0)
            for s in [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]
        )
        resolved_count = status_counts.get(AlertStatus.RESOLVED.value, 0)

        # Financial impact (active alerts only)
        financial_query = select(
            func.sum(SLAAlert.estimated_credit),
            func.sum(SLAAlert.at_risk_amount),
        ).where(
            SLAAlert.has_financial_impact == True,
            SLAAlert.status.in_([
                AlertStatus.ACTIVE,
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.IN_PROGRESS,
            ])
        )
        financial_query = apply_filters(financial_query)
        financial_result = await self.db.execute(financial_query)
        financial_row = financial_result.fetchone()
        total_credits_due = float(financial_row[0] or 0)
        total_at_risk = float(financial_row[1] or 0)

        return {
            "active_count": active_count,
            "resolved_count": resolved_count,
            "by_status": status_counts,
            "by_priority": priority_counts,
            "by_category": category_counts,
            "financial_impact": {
                "credits_due": total_credits_due,
                "at_risk": total_at_risk,
            },
            "critical_count": priority_counts.get(AlertPriority.CRITICAL.value, 0),
            "high_count": priority_counts.get(AlertPriority.HIGH.value, 0),
        }

    async def send_alert_notification(
        self,
        alert: SLAAlert,
        recipient_email: str,
        recipient_name: str = "",
        template_name: str = "sla_breach_alert",
    ) -> bool:
        """Send notification for an alert.

        Args:
            alert: The alert to notify about.
            recipient_email: Recipient email address.
            recipient_name: Recipient display name.
            template_name: Notification template to use.

        Returns:
            True if notification was sent successfully.
        """
        # Build context from alert
        context = {
            "alert_id": str(alert.id),
            "category": alert.category.value,
            "priority": alert.priority.value,
            "title": alert.title,
            "description": alert.description,
            "sla_reference": alert.sla_reference or "",
            "sla_name": alert.sla_name or "",
            "target_value": float(alert.target_value) if alert.target_value else 0,
            "actual_value": float(alert.actual_value) if alert.actual_value else 0,
            "deviation_percent": float(alert.deviation_percentage) if alert.deviation_percentage else 0,
            "breach_severity": alert.breach_severity.value if alert.breach_severity else "",
            "has_financial_impact": alert.has_financial_impact,
            "credit_amount": float(alert.estimated_credit) if alert.estimated_credit else 0,
            "at_risk_amount": float(alert.at_risk_amount) if alert.at_risk_amount else 0,
            "detected_at": alert.detected_at.strftime("%Y-%m-%d %H:%M") if alert.detected_at else "",
            "source_system": alert.source_system or "System",
            "recipient_name": recipient_name,
        }

        # Get contract info
        result = await self.db.execute(
            select(Contract).where(Contract.id == alert.contract_id)
        )
        contract = result.scalar_one_or_none()
        if contract:
            context["contract_name"] = contract.filename
            context["counterparty"] = contract.counterparty or "N/A"

        notification = await self.notification_service.send_notification(
            template_name=template_name,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            context=context,
        )

        # Update alert with notification info
        if notification.status == NotificationStatus.sent:
            alert.notification_sent = True
            alert.notification_sent_at = datetime.utcnow()
            alert.notification_log_id = notification.id
            await self.db.flush()
            return True

        return False

    async def _send_escalation_notification(
        self,
        alert: SLAAlert,
        escalate_to: str,
    ) -> None:
        """Send escalation notification."""
        context = {
            "escalation_level": alert.escalation_level,
            "title": alert.title,
            "description": alert.description,
            "priority": alert.priority.value.upper(),
            "days_open": alert.days_open,
        }

        await self.notification_service.send_notification(
            template_name="alert_escalation",
            recipient_email=escalate_to,
            context=context,
        )


async def get_sla_alert_service(db: AsyncSession) -> SLAAlertService:
    """Factory function for SLA alert service."""
    return SLAAlertService(db)
