"""Progress tracking service for contract processing.

Provides real-time progress updates via Server-Sent Events (SSE).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class ProcessingStage(str, Enum):
    """Stages of contract processing."""

    # Indexer stages
    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    CLASSIFYING = "classifying"
    METADATA = "metadata"
    CUSTOM_FIELDS = "custom_fields"
    RISK = "risk"
    KNOWLEDGE_GRAPH = "knowledge_graph"

    # Deep analysis stages
    CLAUSE_EXTRACTION = "clause_extraction"
    OBLIGATION_DETECTION = "obligation_detection"
    SLA_EXTRACTION = "sla_extraction"
    RENEWAL_ANALYSIS = "renewal_analysis"
    SCHEMA_EXTRACTION = "schema_extraction"
    LINK_DETECTION = "link_detection"
    COMPLIANCE_CHECK = "compliance_check"
    GOVERNANCE_BRIDGE = "governance_bridge"

    # Terminal stages
    COMPLETED = "completed"
    FAILED = "failed"


# Human-readable stage descriptions
STAGE_DESCRIPTIONS = {
    ProcessingStage.QUEUED: "Queued for processing",
    ProcessingStage.PARSING: "Parsing document",
    ProcessingStage.CHUNKING: "Splitting into sections",
    ProcessingStage.CLASSIFYING: "Classifying sections",
    ProcessingStage.METADATA: "Extracting metadata",
    ProcessingStage.CUSTOM_FIELDS: "Extracting custom fields",
    ProcessingStage.RISK: "Assessing risk",
    ProcessingStage.KNOWLEDGE_GRAPH: "Extracting references",
    ProcessingStage.CLAUSE_EXTRACTION: "Extracting clauses",
    ProcessingStage.OBLIGATION_DETECTION: "Detecting obligations",
    ProcessingStage.SLA_EXTRACTION: "Extracting SLAs",
    ProcessingStage.RENEWAL_ANALYSIS: "Analyzing renewal terms",
    ProcessingStage.SCHEMA_EXTRACTION: "Structured data extraction",
    ProcessingStage.LINK_DETECTION: "Finding related contracts",
    ProcessingStage.COMPLIANCE_CHECK: "Checking compliance",
    ProcessingStage.GOVERNANCE_BRIDGE: "Setting up governance",
    ProcessingStage.COMPLETED: "Processing complete",
    ProcessingStage.FAILED: "Processing failed",
}

# Stage weights for progress percentage (total = 100)
STAGE_WEIGHTS = {
    ProcessingStage.QUEUED: 0,
    ProcessingStage.PARSING: 5,
    ProcessingStage.CHUNKING: 8,
    ProcessingStage.CLASSIFYING: 12,
    ProcessingStage.METADATA: 20,
    ProcessingStage.CUSTOM_FIELDS: 25,
    ProcessingStage.RISK: 30,
    ProcessingStage.KNOWLEDGE_GRAPH: 35,
    ProcessingStage.CLAUSE_EXTRACTION: 45,
    ProcessingStage.OBLIGATION_DETECTION: 55,
    ProcessingStage.SLA_EXTRACTION: 63,
    ProcessingStage.RENEWAL_ANALYSIS: 70,
    ProcessingStage.SCHEMA_EXTRACTION: 76,
    ProcessingStage.LINK_DETECTION: 82,
    ProcessingStage.COMPLIANCE_CHECK: 88,
    ProcessingStage.GOVERNANCE_BRIDGE: 94,
    ProcessingStage.COMPLETED: 100,
    ProcessingStage.FAILED: 100,
}

# Ordered list of all stages for frontend rendering
STAGE_ORDER = [
    ProcessingStage.QUEUED,
    ProcessingStage.PARSING,
    ProcessingStage.CHUNKING,
    ProcessingStage.CLASSIFYING,
    ProcessingStage.METADATA,
    ProcessingStage.CUSTOM_FIELDS,
    ProcessingStage.RISK,
    ProcessingStage.KNOWLEDGE_GRAPH,
    ProcessingStage.CLAUSE_EXTRACTION,
    ProcessingStage.OBLIGATION_DETECTION,
    ProcessingStage.SLA_EXTRACTION,
    ProcessingStage.RENEWAL_ANALYSIS,
    ProcessingStage.SCHEMA_EXTRACTION,
    ProcessingStage.LINK_DETECTION,
    ProcessingStage.COMPLIANCE_CHECK,
    ProcessingStage.GOVERNANCE_BRIDGE,
    ProcessingStage.COMPLETED,
]


@dataclass
class ProcessingProgress:
    """Progress state for a contract being processed."""

    contract_id: str
    stage: ProcessingStage = ProcessingStage.QUEUED
    progress_percent: int = 0
    message: str = ""
    error: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for SSE."""
        return {
            "contract_id": self.contract_id,
            "stage": self.stage.value,
            "stage_description": STAGE_DESCRIPTIONS.get(self.stage, self.stage.value),
            "progress_percent": self.progress_percent,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "details": self.details,
            "stages": [
                {
                    "id": s.value,
                    "label": STAGE_DESCRIPTIONS.get(s, s.value),
                    "weight": STAGE_WEIGHTS.get(s, 0),
                }
                for s in STAGE_ORDER
            ],
        }


class ProgressTracker:
    """In-memory progress tracker with SSE support.

    Tracks processing progress for contracts and notifies
    subscribers via async events.
    """

    def __init__(self):
        self._progress: dict[str, ProcessingProgress] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._subscribers: dict[str, int] = {}  # contract_id -> subscriber count

    def start_tracking(self, contract_id: str) -> ProcessingProgress:
        """Start tracking progress for a contract.

        Args:
            contract_id: Contract ID to track.

        Returns:
            New ProcessingProgress instance.
        """
        progress = ProcessingProgress(
            contract_id=contract_id,
            stage=ProcessingStage.QUEUED,
            progress_percent=0,
            message="Starting processing...",
        )
        self._progress[contract_id] = progress
        self._events[contract_id] = asyncio.Event()
        logger.debug(f"Started tracking progress for {contract_id}")
        return progress

    def update_progress(
        self,
        contract_id: str,
        stage: ProcessingStage,
        message: str | None = None,
        details: dict | None = None,
        error: str | None = None,
    ) -> ProcessingProgress | None:
        """Update progress for a contract.

        Args:
            contract_id: Contract ID.
            stage: Current processing stage.
            message: Optional status message.
            details: Optional additional details.
            error: Optional error message (for FAILED stage).

        Returns:
            Updated ProcessingProgress or None if not found.
        """
        progress = self._progress.get(contract_id)
        if not progress:
            # Auto-start tracking if not started
            progress = self.start_tracking(contract_id)

        progress.stage = stage
        progress.progress_percent = STAGE_WEIGHTS.get(stage, 0)
        progress.message = message or STAGE_DESCRIPTIONS.get(stage, "")
        progress.updated_at = datetime.utcnow()
        progress.error = error

        if details:
            progress.details.update(details)

        # Notify subscribers
        event = self._events.get(contract_id)
        if event:
            event.set()

        logger.debug(f"Progress update for {contract_id}: {stage.value} ({progress.progress_percent}%)")
        return progress

    def get_progress(self, contract_id: str) -> ProcessingProgress | None:
        """Get current progress for a contract.

        Args:
            contract_id: Contract ID.

        Returns:
            ProcessingProgress or None if not found.
        """
        return self._progress.get(contract_id)

    def stop_tracking(self, contract_id: str) -> None:
        """Stop tracking progress for a contract.

        Args:
            contract_id: Contract ID.
        """
        self._progress.pop(contract_id, None)
        event = self._events.pop(contract_id, None)
        if event:
            event.set()  # Wake up any waiters
        self._subscribers.pop(contract_id, None)
        logger.debug(f"Stopped tracking progress for {contract_id}")

    async def subscribe(
        self,
        contract_id: str,
        timeout: float = 30.0,
    ) -> AsyncGenerator[ProcessingProgress, None]:
        """Subscribe to progress updates for a contract.

        Yields progress updates as they occur. Used by SSE endpoint.

        Args:
            contract_id: Contract ID to subscribe to.
            timeout: Timeout between updates (sends keepalive).

        Yields:
            ProcessingProgress updates.
        """
        # Track subscriber
        self._subscribers[contract_id] = self._subscribers.get(contract_id, 0) + 1

        try:
            # Ensure event exists
            if contract_id not in self._events:
                self._events[contract_id] = asyncio.Event()

            event = self._events[contract_id]

            # Yield current state immediately
            progress = self._progress.get(contract_id)
            if progress:
                yield progress

            # Wait for updates
            while True:
                event.clear()

                try:
                    await asyncio.wait_for(event.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    # Send keepalive (yield current state)
                    progress = self._progress.get(contract_id)
                    if progress:
                        yield progress
                    continue

                # Check if still tracking
                progress = self._progress.get(contract_id)
                if not progress:
                    break

                yield progress

                # Stop if completed or failed
                if progress.stage in (ProcessingStage.COMPLETED, ProcessingStage.FAILED):
                    break

        finally:
            # Unsubscribe
            self._subscribers[contract_id] = max(0, self._subscribers.get(contract_id, 1) - 1)

            # Clean up if no more subscribers and completed
            if self._subscribers.get(contract_id, 0) == 0:
                progress = self._progress.get(contract_id)
                if progress and progress.stage in (ProcessingStage.COMPLETED, ProcessingStage.FAILED):
                    # Keep for a bit in case of reconnection, then clean up
                    await asyncio.sleep(5)
                    if self._subscribers.get(contract_id, 0) == 0:
                        self.stop_tracking(contract_id)


# Singleton instance
_tracker: ProgressTracker | None = None


def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker instance.

    Returns:
        ProgressTracker singleton.
    """
    global _tracker
    if _tracker is None:
        _tracker = ProgressTracker()
    return _tracker
