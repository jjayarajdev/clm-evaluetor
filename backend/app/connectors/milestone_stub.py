"""Milestone Stub Connector.

Provides simulated project milestone data for demo purposes.
Based on typical IT outsourcing contract deliverables and transition milestones.
"""

import logging
import random
from datetime import date, timedelta
from decimal import Decimal

from app.connectors.base import (
    ConnectorResult,
    ConnectorType,
    DataQuality,
    MilestoneStatus,
    ProjectConnector,
)

logger = logging.getLogger(__name__)


# Realistic milestone configurations based on ING contract structure
# Maps to Critical Deliverables from Service Level Matrix (Attachment 3-C)
MILESTONE_CONFIGURATIONS = {
    "MS-2.1": {
        "name": "Transition & Transformation Plan",
        "description": "Complete T&T plan with detailed timelines",
        "baseline_days_from_start": 60,  # 2 months after MOU
        "dependencies": [],
        "credit_at_risk": Decimal("50000"),
    },
    "MS-2.2": {
        "name": "HR Transfer Plan",
        "description": "Detailed plan for employee transitions",
        "baseline_days_from_start": 60,
        "dependencies": ["MS-2.1"],
        "credit_at_risk": Decimal("25000"),
    },
    "MS-2.3": {
        "name": "Policies & Procedures Including Security",
        "description": "Complete documentation of all operational procedures",
        "baseline_days_from_start": 210,  # 7 months after commencement
        "dependencies": ["MS-2.1", "MS-2.2"],
        "credit_at_risk": Decimal("75000"),
    },
    "MS-2.4": {
        "name": "First Set of Critical Reports",
        "description": "Initial reporting framework and dashboards",
        "baseline_days_from_start": 150,  # 5 months after commencement
        "dependencies": ["MS-2.1"],
        "credit_at_risk": Decimal("30000"),
    },
    "MS-2.5": {
        "name": "Service Catalogue",
        "description": "Complete service catalog with pricing",
        "baseline_days_from_start": 90,  # 3 months after commencement
        "dependencies": ["MS-2.1"],
        "credit_at_risk": Decimal("40000"),
    },
    "MS-2.6": {
        "name": "Exit Plan Framework",
        "description": "Framework for contract exit and transition",
        "baseline_days_from_start": 210,
        "dependencies": ["MS-2.3"],
        "credit_at_risk": Decimal("35000"),
    },
    "MS-3.1": {
        "name": "Knowledge Transfer Phase 1",
        "description": "Initial knowledge transfer from incumbent",
        "baseline_days_from_start": 45,
        "dependencies": [],
        "credit_at_risk": Decimal("60000"),
    },
    "MS-3.2": {
        "name": "Knowledge Transfer Phase 2",
        "description": "Advanced knowledge transfer and validation",
        "baseline_days_from_start": 90,
        "dependencies": ["MS-3.1"],
        "credit_at_risk": Decimal("60000"),
    },
    "MS-4.1": {
        "name": "Go-Live Wave 1 - Desktop Services",
        "description": "Production cutover for desktop services",
        "baseline_days_from_start": 120,
        "dependencies": ["MS-2.1", "MS-3.1", "MS-2.5"],
        "credit_at_risk": Decimal("150000"),
    },
    "MS-4.2": {
        "name": "Go-Live Wave 2 - Network Services",
        "description": "Production cutover for network services",
        "baseline_days_from_start": 150,
        "dependencies": ["MS-4.1"],
        "credit_at_risk": Decimal("100000"),
    },
    "MS-4.3": {
        "name": "Go-Live Wave 3 - Full Operations",
        "description": "Complete transition to steady state",
        "baseline_days_from_start": 180,
        "dependencies": ["MS-4.1", "MS-4.2"],
        "credit_at_risk": Decimal("200000"),
    },
    "MS-5.1": {
        "name": "Hypercare Period Complete",
        "description": "End of enhanced support period",
        "baseline_days_from_start": 270,  # 9 months
        "dependencies": ["MS-4.3"],
        "credit_at_risk": Decimal("50000"),
    },
}


class MilestoneStubConnector(ProjectConnector):
    """Stub Project connector for milestone tracking."""

    connector_name = "Project Management (Stub)"
    is_stub = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._seed = config.get("seed", 42) if config else 42
        self._project_start = config.get("project_start", date(2025, 1, 15)) if config else date(2025, 1, 15)
        random.seed(self._seed)

    async def connect(self) -> bool:
        """Simulate connection."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    async def health_check(self) -> ConnectorResult:
        """Return healthy status."""
        return ConnectorResult(
            success=True,
            data={"status": "healthy", "projects_tracked": 1},
            quality=DataQuality.SIMULATED,
            source="Project Management Stub",
        )

    async def get_milestone_status(
        self,
        project_id: str | None = None,
        milestone_ids: list[str] | None = None,
    ) -> ConnectorResult:
        """Get status of project milestones.

        Args:
            project_id: Optional project ID (ignored in stub).
            milestone_ids: Optional list of specific milestones.

        Returns:
            ConnectorResult with milestone statuses.
        """
        milestones = []
        today = date.today()

        # Filter milestones if specific IDs requested
        configs = MILESTONE_CONFIGURATIONS
        if milestone_ids:
            configs = {k: v for k, v in configs.items() if k in milestone_ids}

        for ms_id, config in configs.items():
            milestone = self._generate_milestone_status(ms_id, config, today)
            milestones.append(milestone)

        # Sort by planned date
        milestones.sort(key=lambda m: m.planned_date)

        return ConnectorResult(
            success=True,
            data=milestones,
            quality=DataQuality.SIMULATED,
            source="Project Management Stub",
            metadata={
                "project_start": self._project_start.isoformat(),
                "milestone_count": len(milestones),
            },
        )

    async def get_milestone_timeline(self) -> ConnectorResult:
        """Get full milestone timeline with Gantt-style data.

        Returns:
            ConnectorResult with timeline data.
        """
        milestones, _ = await self.get_milestone_status()

        timeline = {
            "project_start": self._project_start.isoformat(),
            "project_end_planned": (self._project_start + timedelta(days=365)).isoformat(),
            "milestones": [
                {
                    "id": m.milestone_id,
                    "name": m.milestone_name,
                    "planned_start": (m.planned_date - timedelta(days=14)).isoformat(),
                    "planned_end": m.planned_date.isoformat(),
                    "actual_end": m.actual_date.isoformat() if m.actual_date else None,
                    "status": m.status,
                    "completion": m.completion_percentage,
                    "dependencies": m.dependencies,
                    "variance_days": m.days_variance,
                }
                for m in milestones.data
            ],
            "summary": {
                "total": len(milestones.data),
                "completed": sum(1 for m in milestones.data if m.status == "completed"),
                "in_progress": sum(1 for m in milestones.data if m.status == "in_progress"),
                "delayed": sum(1 for m in milestones.data if m.status == "delayed"),
                "at_risk": sum(1 for m in milestones.data if m.status == "at_risk"),
                "pending": sum(1 for m in milestones.data if m.status == "pending"),
            },
        }

        return ConnectorResult(
            success=True,
            data=timeline,
            quality=DataQuality.SIMULATED,
            source="Project Management Stub",
        )

    def _generate_milestone_status(
        self,
        ms_id: str,
        config: dict,
        today: date,
    ) -> MilestoneStatus:
        """Generate realistic milestone status.

        Creates scenarios with:
        - Some milestones completed on time
        - Some completed early
        - Some delayed
        - Some at risk
        - Future milestones pending or in progress
        """
        planned_date = self._project_start + timedelta(days=config["baseline_days_from_start"])

        # Add some planned date variance (-5 to +10 days)
        planned_variance = random.randint(-5, 10)
        planned_date = planned_date + timedelta(days=planned_variance)

        # Determine status based on date and randomness
        days_until_due = (planned_date - today).days

        if days_until_due < -30:
            # Should have been done a month ago
            if random.random() < 0.9:
                # 90% completed
                status = "completed"
                # Actual completion: some early, some late
                delay = random.randint(-7, 14)
                actual_date = planned_date + timedelta(days=delay)
                completion = 100
            else:
                # 10% severely delayed
                status = "delayed"
                actual_date = None
                completion = random.randint(70, 95)
                delay = abs(days_until_due)

        elif days_until_due < 0:
            # Past due but recent
            if random.random() < 0.7:
                status = "completed"
                delay = random.randint(0, abs(days_until_due) + 5)
                actual_date = planned_date + timedelta(days=delay)
                completion = 100
            else:
                status = "delayed"
                actual_date = None
                completion = random.randint(80, 98)
                delay = abs(days_until_due)

        elif days_until_due <= 14:
            # Due within 2 weeks
            if random.random() < 0.3:
                # Some completed early
                status = "completed"
                delay = random.randint(-10, -1)
                actual_date = planned_date + timedelta(days=delay)
                completion = 100
            elif random.random() < 0.7:
                status = "in_progress"
                actual_date = None
                completion = random.randint(75, 95)
                delay = 0
            else:
                status = "at_risk"
                actual_date = None
                completion = random.randint(50, 75)
                delay = random.randint(5, 15)

        elif days_until_due <= 60:
            # Due within 2 months
            if random.random() < 0.6:
                status = "in_progress"
                completion = random.randint(20, 60)
            elif random.random() < 0.8:
                status = "pending"
                completion = random.randint(0, 20)
            else:
                status = "at_risk"
                completion = random.randint(10, 40)
            actual_date = None
            delay = 0

        else:
            # Future milestone
            status = "pending"
            actual_date = None
            completion = 0
            delay = 0

        # Generate notes based on status
        notes = self._generate_notes(status, completion, delay, config)

        return MilestoneStatus(
            milestone_id=ms_id,
            milestone_name=config["name"],
            planned_date=planned_date,
            actual_date=actual_date,
            status=status,
            days_variance=delay if status == "completed" else (delay if status in ["delayed", "at_risk"] else 0),
            completion_percentage=completion,
            dependencies=config.get("dependencies", []),
            notes=notes,
        )

    def _generate_notes(self, status: str, completion: int, delay: int, config: dict) -> str:
        """Generate contextual notes for milestone."""
        if status == "completed":
            if delay < 0:
                return f"Completed {abs(delay)} days ahead of schedule."
            elif delay == 0:
                return "Completed on schedule."
            else:
                return f"Completed {delay} days late. Credit at risk: ${config['credit_at_risk']:,}"

        elif status == "delayed":
            return f"Currently {delay} days behind schedule. {completion}% complete. Escalation required. Credit at risk: ${config['credit_at_risk']:,}"

        elif status == "at_risk":
            return f"At risk of delay. {completion}% complete. Mitigation actions in progress."

        elif status == "in_progress":
            return f"On track. {completion}% complete."

        else:
            return "Not yet started."


def get_milestone_stub() -> MilestoneStubConnector:
    """Get Milestone stub connector instance."""
    return MilestoneStubConnector()
