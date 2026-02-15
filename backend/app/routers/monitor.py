"""API endpoints for contract monitoring and workflow execution.

Provides endpoints for:
- Running on-demand scans
- Viewing and managing events
- Approving/rejecting approval requests
- Viewing workflow execution status
- Generating test data
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.approval import ApprovalRequest, ApprovalStatus
from app.models.event import Event, EventStatus, EventType
from app.models.workflow import ActionExecution, ExecutionStatus, WorkflowDefinition
from app.workflows import run_on_demand_scan, run_on_demand_processing
from app.workflows.orchestrator import WorkflowOrchestrator
from app.generators import generate_test_data

router = APIRouter(prefix="/monitor", tags=["monitor"])


# Request/Response Models

class ScanResponse(BaseModel):
    """Response for scan operation."""
    success: bool
    message: str
    events_detected: int
    details: dict


class ProcessResponse(BaseModel):
    """Response for processing operation."""
    success: bool
    message: str
    events_processed: int
    details: dict


class EventSummary(BaseModel):
    """Summary of an event."""
    id: str
    event_type: str
    severity: str
    status: str
    title: str
    contract_id: str
    detected_at: datetime
    workflow_name: Optional[str] = None


class EventDetail(BaseModel):
    """Detailed event information."""
    id: str
    event_type: str
    severity: str
    status: str
    title: str
    description: Optional[str]
    contract_id: str
    details: Optional[dict]
    detected_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    workflow_id: Optional[str]
    workflow_name: Optional[str]
    action_executions: list[dict]


class ApprovalSummary(BaseModel):
    """Summary of an approval request."""
    id: str
    title: str
    status: str
    requested_at: datetime
    expires_at: Optional[datetime]
    action_type: Optional[str]
    event_title: Optional[str]


class ApprovalDecision(BaseModel):
    """Request to approve or reject."""
    decision: str  # "approve" or "reject"
    notes: Optional[str] = None
    reason: Optional[str] = None  # For rejection


class TestDataRequest(BaseModel):
    """Request to generate test data."""
    scenario: Optional[str] = None
    breach_count: int = 3
    warning_count: int = 2


class MonitorStats(BaseModel):
    """Monitoring statistics."""
    total_events: int
    pending_events: int
    processing_events: int
    completed_events: int
    failed_events: int
    pending_approvals: int
    events_by_type: dict
    events_last_24h: int


# Endpoints

@router.post("/scan", response_model=ScanResponse)
async def run_scan(
    db: AsyncSession = Depends(get_db),
):
    """Run an on-demand event detection scan.

    Scans all contracts for:
    - SLA breaches
    - SLA warnings
    - Upcoming renewals
    - Overdue milestones
    - Due obligations
    """
    try:
        results = await run_on_demand_scan(db)
        return ScanResponse(
            success=True,
            message="Scan completed successfully",
            events_detected=results.get("total_events", 0),
            details=results,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process", response_model=ProcessResponse)
async def run_processing(
    db: AsyncSession = Depends(get_db),
):
    """Run workflow processing for pending events.

    Processes pending events and continues in-progress workflows.
    """
    try:
        results = await run_on_demand_processing(db)
        total = results.get("pending_processed", 0) + results.get("in_progress_processed", 0)
        return ProcessResponse(
            success=True,
            message="Processing completed",
            events_processed=total,
            details=results,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=MonitorStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get monitoring statistics."""
    # Total events by status
    status_counts = {}
    for status in EventStatus:
        result = await db.execute(
            select(func.count(Event.id)).where(Event.status == status)
        )
        status_counts[status.value] = result.scalar() or 0

    # Events by type
    type_counts = {}
    for event_type in EventType:
        result = await db.execute(
            select(func.count(Event.id)).where(Event.event_type == event_type)
        )
        type_counts[event_type.value] = result.scalar() or 0

    # Pending approvals
    approval_result = await db.execute(
        select(func.count(ApprovalRequest.id)).where(
            ApprovalRequest.status == ApprovalStatus.pending
        )
    )
    pending_approvals = approval_result.scalar() or 0

    # Events in last 24 hours
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_result = await db.execute(
        select(func.count(Event.id)).where(Event.detected_at >= cutoff)
    )
    events_24h = recent_result.scalar() or 0

    return MonitorStats(
        total_events=sum(status_counts.values()),
        pending_events=status_counts.get("pending", 0),
        processing_events=status_counts.get("processing", 0) + status_counts.get("executing", 0),
        completed_events=status_counts.get("completed", 0),
        failed_events=status_counts.get("failed", 0),
        pending_approvals=pending_approvals,
        events_by_type=type_counts,
        events_last_24h=events_24h,
    )


@router.get("/events", response_model=list[EventSummary])
async def list_events(
    status: Optional[EventStatus] = None,
    event_type: Optional[EventType] = None,
    limit: int = Query(default=50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List events with optional filters."""
    query = select(Event).options(selectinload(Event.workflow))

    if status:
        query = query.where(Event.status == status)
    if event_type:
        query = query.where(Event.event_type == event_type)

    query = query.order_by(Event.detected_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        EventSummary(
            id=str(e.id),
            event_type=e.event_type.value,
            severity=e.severity.value,
            status=e.status.value,
            title=e.title,
            contract_id=str(e.contract_id),
            detected_at=e.detected_at,
            workflow_name=e.workflow.name if e.workflow else None,
        )
        for e in events
    ]


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed event information."""
    result = await db.execute(
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.workflow),
            selectinload(Event.action_executions),
        )
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get action execution details
    executions = []
    for exec in event.action_executions:
        executions.append({
            "id": str(exec.id),
            "action_type": exec.action_type.value,
            "status": exec.status.value,
            "attempts": exec.attempts,
            "started_at": exec.started_at.isoformat() if exec.started_at else None,
            "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
            "result": exec.result,
            "error_message": exec.error_message,
            "external_id": exec.external_id,
        })

    return EventDetail(
        id=str(event.id),
        event_type=event.event_type.value,
        severity=event.severity.value,
        status=event.status.value,
        title=event.title,
        description=event.description,
        contract_id=str(event.contract_id),
        details=event.details,
        detected_at=event.detected_at,
        started_at=event.started_at,
        completed_at=event.completed_at,
        error_message=event.error_message,
        workflow_id=str(event.workflow_id) if event.workflow_id else None,
        workflow_name=event.workflow.name if event.workflow else None,
        action_executions=executions,
    )


@router.get("/approvals", response_model=list[ApprovalSummary])
async def list_approvals(
    status: Optional[ApprovalStatus] = None,
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List approval requests."""
    query = (
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.action_execution))
    )

    if status:
        query = query.where(ApprovalRequest.status == status)

    query = query.order_by(ApprovalRequest.requested_at.desc()).limit(limit)

    result = await db.execute(query)
    approvals = result.scalars().all()

    summaries = []
    for a in approvals:
        # Get event title if available
        event_title = None
        if a.action_execution:
            event_result = await db.execute(
                select(Event).where(Event.id == a.action_execution.event_id)
            )
            event = event_result.scalar_one_or_none()
            if event:
                event_title = event.title

        summaries.append(ApprovalSummary(
            id=str(a.id),
            title=a.title,
            status=a.status.value,
            requested_at=a.requested_at,
            expires_at=a.expires_at,
            action_type=a.action_execution.action_type.value if a.action_execution else None,
            event_title=event_title,
        ))

    return summaries


@router.post("/approvals/{approval_id}/decide")
async def decide_approval(
    approval_id: UUID,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject an approval request."""
    orchestrator = WorkflowOrchestrator(db)

    # For now, use a placeholder user ID
    # In production, get from authentication
    user_id = UUID("00000000-0000-0000-0000-000000000001")

    if decision.decision == "approve":
        success = await orchestrator.approve_request(
            approval_id,
            user_id,
            notes=decision.notes,
        )
        message = "Approved successfully" if success else "Failed to approve"
    elif decision.decision == "reject":
        if not decision.reason:
            raise HTTPException(status_code=400, detail="Rejection reason required")
        success = await orchestrator.reject_request(
            approval_id,
            user_id,
            reason=decision.reason,
        )
        message = "Rejected successfully" if success else "Failed to reject"
    else:
        raise HTTPException(status_code=400, detail="Invalid decision. Use 'approve' or 'reject'")

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": success, "message": message}


@router.get("/workflows", response_model=list[dict])
async def list_workflows(
    db: AsyncSession = Depends(get_db),
):
    """List all workflow definitions."""
    result = await db.execute(
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.steps))
        .order_by(WorkflowDefinition.name)
    )
    workflows = result.scalars().all()

    return [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "event_type": w.event_type.value,
            "is_active": w.is_active,
            "is_default": w.is_default,
            "step_count": len(w.steps),
            "steps": [
                {
                    "name": s.name,
                    "order": s.step_order,
                    "action_type": s.action_type.value,
                    "requires_approval": s.requires_approval,
                }
                for s in sorted(w.steps, key=lambda x: x.step_order)
            ],
        }
        for w in workflows
    ]


@router.post("/test-data")
async def create_test_data(
    request: TestDataRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate synthetic test data.

    Creates test scenarios for demonstrating the system:
    - SLA breaches that trigger workflows
    - Warning-level measurements
    - Upcoming renewals
    - Overdue milestones
    """
    try:
        if request.scenario:
            results = await generate_test_data(db, scenario=request.scenario)
        else:
            from app.generators.synthetic_data import SyntheticDataGenerator
            generator = SyntheticDataGenerator(db)
            results = await generator.generate_all(
                breach_count=request.breach_count,
                warning_count=request.warning_count,
            )

        return {
            "success": True,
            "message": "Test data generated",
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-scenario")
async def run_scenario(
    scenario: str = Query(default="sla_breach", description="Scenario type"),
    db: AsyncSession = Depends(get_db),
):
    """Run a complete end-to-end scenario.

    Creates test data, runs detection, and processes workflows.

    Available scenarios:
    - sla_breach: SLA breach with full workflow
    - sla_warning: SLA warning notification
    - renewal: Contract renewal approaching
    - milestone_overdue: Overdue milestone
    """
    results = {
        "scenario": scenario,
        "steps": [],
    }

    try:
        # Step 1: Generate scenario data
        from app.generators.synthetic_data import SyntheticDataGenerator
        generator = SyntheticDataGenerator(db)
        scenario_data = await generator.create_test_scenario(scenario)
        results["steps"].append({
            "step": "generate_data",
            "success": True,
            "data": scenario_data,
        })

        # Step 2: Run event detection
        scan_results = await run_on_demand_scan(db)
        results["steps"].append({
            "step": "detect_events",
            "success": True,
            "events_detected": scan_results.get("total_events", 0),
        })

        # Step 3: Process workflows
        process_results = await run_on_demand_processing(db)
        results["steps"].append({
            "step": "process_workflows",
            "success": True,
            "events_processed": process_results.get("pending_processed", 0),
        })

        results["success"] = True
        results["message"] = f"Scenario '{scenario}' executed successfully"

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))

    return results
