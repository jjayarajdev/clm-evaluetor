"""Monitor Service - Scheduled scanning and workflow execution.

This service runs on a schedule to detect events and process workflows.
Can be run as a background task or triggered on-demand via API.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.workflows.event_detector import EventDetector
from app.workflows.orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


class MonitorService:
    """Background service for continuous contract monitoring.

    Runs periodic scans to detect events and process workflows.
    Supports both scheduled execution and on-demand triggers.
    """

    def __init__(
        self,
        scan_interval_seconds: int = 300,  # 5 minutes
        processing_interval_seconds: int = 60,  # 1 minute
    ):
        """Initialize monitor service.

        Args:
            scan_interval_seconds: Interval between full event scans.
            processing_interval_seconds: Interval between workflow processing runs.
        """
        self.scan_interval = scan_interval_seconds
        self.processing_interval = processing_interval_seconds
        self._running = False
        self._last_scan: Optional[datetime] = None
        self._last_process: Optional[datetime] = None
        self._stats = {
            "total_scans": 0,
            "total_events_detected": 0,
            "total_events_processed": 0,
            "total_approvals_checked": 0,
            "errors": 0,
        }

    @property
    def stats(self) -> dict:
        """Get monitoring statistics."""
        return {
            **self._stats,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "last_process": self._last_process.isoformat() if self._last_process else None,
            "is_running": self._running,
        }

    async def start(self) -> None:
        """Start the background monitoring loop."""
        if self._running:
            logger.warning("Monitor service already running")
            return

        self._running = True
        logger.info("Starting monitor service")

        # Run both loops concurrently
        await asyncio.gather(
            self._scan_loop(),
            self._process_loop(),
        )

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        logger.info("Stopping monitor service")

    async def _scan_loop(self) -> None:
        """Event detection loop."""
        while self._running:
            try:
                await self.run_detection_scan()
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                self._stats["errors"] += 1

            await asyncio.sleep(self.scan_interval)

    async def _process_loop(self) -> None:
        """Workflow processing loop."""
        while self._running:
            try:
                await self.run_workflow_processing()
            except Exception as e:
                logger.error(f"Error in process loop: {e}")
                self._stats["errors"] += 1

            await asyncio.sleep(self.processing_interval)

    async def run_detection_scan(self, db: Optional[AsyncSession] = None) -> dict:
        """Run a single event detection scan.

        Args:
            db: Optional session (creates one if not provided).

        Returns:
            Scan results summary.
        """
        logger.info("Running event detection scan")

        should_close = db is None
        if db is None:
            db = async_session_maker()

        try:
            detector = EventDetector(db)
            results = await detector.run_full_scan()

            self._last_scan = datetime.utcnow()
            self._stats["total_scans"] += 1
            self._stats["total_events_detected"] += results["total_events"]

            logger.info(f"Scan complete: {results['total_events']} events detected")
            return results

        finally:
            if should_close:
                await db.close()

    async def run_workflow_processing(self, db: Optional[AsyncSession] = None) -> dict:
        """Run a single workflow processing cycle.

        Args:
            db: Optional session (creates one if not provided).

        Returns:
            Processing results summary.
        """
        logger.info("Running workflow processing")

        should_close = db is None
        if db is None:
            db = async_session_maker()

        try:
            orchestrator = WorkflowOrchestrator(db)

            # Register action handlers
            self._register_action_handlers(orchestrator)

            # Process pending events
            pending_processed = await orchestrator.process_pending_events(limit=20)

            # Continue in-progress events
            in_progress_processed = await orchestrator.continue_in_progress_events(limit=20)

            # Check approvals
            approvals_processed = await orchestrator.check_pending_approvals()

            self._last_process = datetime.utcnow()
            self._stats["total_events_processed"] += pending_processed + in_progress_processed
            self._stats["total_approvals_checked"] += approvals_processed

            results = {
                "pending_processed": pending_processed,
                "in_progress_processed": in_progress_processed,
                "approvals_processed": approvals_processed,
            }

            logger.info(f"Processing complete: {results}")
            return results

        finally:
            if should_close:
                await db.close()

    def _register_action_handlers(self, orchestrator: WorkflowOrchestrator) -> None:
        """Register action handlers with the orchestrator.

        This is where we wire up the actual action implementations.
        """
        from app.actions.handlers import (
            handle_send_email,
            handle_create_snow_incident,
            handle_update_sfdc_account,
            handle_create_sfdc_task,
            handle_calculate_service_credit,
            handle_calculate_penalty,
            handle_update_contract_status,
            handle_create_approval_request,
            handle_escalate,
            handle_webhook,
        )
        from app.models.workflow import ActionType

        orchestrator.register_action_handler(ActionType.send_email, handle_send_email)
        orchestrator.register_action_handler(ActionType.create_snow_incident, handle_create_snow_incident)
        orchestrator.register_action_handler(ActionType.update_sfdc_account, handle_update_sfdc_account)
        orchestrator.register_action_handler(ActionType.create_sfdc_task, handle_create_sfdc_task)
        orchestrator.register_action_handler(ActionType.calculate_service_credit, handle_calculate_service_credit)
        orchestrator.register_action_handler(ActionType.calculate_penalty, handle_calculate_penalty)
        orchestrator.register_action_handler(ActionType.update_contract_status, handle_update_contract_status)
        orchestrator.register_action_handler(ActionType.create_approval_request, handle_create_approval_request)
        orchestrator.register_action_handler(ActionType.escalate, handle_escalate)
        orchestrator.register_action_handler(ActionType.webhook, handle_webhook)


# Singleton instance for the application
_monitor_service: Optional[MonitorService] = None


def get_monitor_service() -> MonitorService:
    """Get or create the monitor service singleton."""
    global _monitor_service
    if _monitor_service is None:
        _monitor_service = MonitorService()
    return _monitor_service


async def run_on_demand_scan(db: AsyncSession) -> dict:
    """Run an on-demand event detection scan.

    Args:
        db: Database session.

    Returns:
        Scan results.
    """
    service = get_monitor_service()
    return await service.run_detection_scan(db)


async def run_on_demand_processing(db: AsyncSession) -> dict:
    """Run on-demand workflow processing.

    Args:
        db: Database session.

    Returns:
        Processing results.
    """
    service = get_monitor_service()
    return await service.run_workflow_processing(db)
