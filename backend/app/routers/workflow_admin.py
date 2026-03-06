"""Admin API endpoints for workflow and notification management.

Provides CRUD operations for:
- Workflow definitions and steps
- Notification templates
- Integration configurations
- Approvers
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.approval import Approver
from app.models.event import EventType
from app.models.integration import IntegrationConfig, IntegrationSystem, IntegrationStatus
from app.models.notification import NotificationTemplate, NotificationChannel, RecipientType
from app.models.user import User
from app.models.workflow import (
    ActionType,
    WorkflowDefinition,
    WorkflowStep,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============== Pydantic Models ==============

class WorkflowCreate(BaseModel):
    """Create a new workflow."""
    name: str
    description: Optional[str] = None
    event_type: str
    is_active: bool = True
    is_default: bool = False
    max_retries: int = 3
    retry_delay_seconds: int = 60
    timeout_seconds: int = 3600
    trigger_conditions: Optional[dict] = None


class WorkflowUpdate(BaseModel):
    """Update a workflow."""
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    max_retries: Optional[int] = None
    trigger_conditions: Optional[dict] = None


class WorkflowStepCreate(BaseModel):
    """Create a workflow step."""
    name: str
    description: Optional[str] = None
    step_order: int
    action_type: str
    action_config: Optional[dict] = None
    requires_approval: bool = False
    approval_timeout_hours: int = 24
    auto_approve_after_timeout: bool = False
    is_optional: bool = False
    continue_on_failure: bool = False
    max_retries: int = 3
    condition: Optional[dict] = None


class TemplateCreate(BaseModel):
    """Create a notification template."""
    name: str
    description: Optional[str] = None
    event_type: Optional[str] = None
    channel: str = "email"
    subject_template: str
    body_template: str
    is_html: bool = False
    html_template: Optional[str] = None
    default_recipient_type: Optional[str] = None


class TemplateUpdate(BaseModel):
    """Update a notification template."""
    name: Optional[str] = None
    description: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    is_html: Optional[bool] = None
    is_active: Optional[bool] = None


class IntegrationCreate(BaseModel):
    """Create an integration configuration."""
    system: str
    name: str
    description: Optional[str] = None
    base_url: str
    auth_type: str = "oauth2"
    credentials: Optional[dict] = None
    config: Optional[dict] = None
    is_active: bool = True
    is_default: bool = False


class IntegrationUpdate(BaseModel):
    """Update an integration."""
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[str] = None
    credentials: Optional[dict] = None
    config: Optional[dict] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ApproverCreate(BaseModel):
    """Add an approver to a workflow."""
    workflow_id: UUID
    user_id: UUID
    is_primary: bool = True
    can_delegate: bool = True
    approval_order: int = 1
    notify_email: bool = True
    notify_slack: bool = False


# ============== Workflow Endpoints ==============

@router.get("/workflows")
async def list_workflows(
    event_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all workflow definitions."""
    query = select(WorkflowDefinition).options(
        selectinload(WorkflowDefinition.steps)
    )

    if event_type:
        query = query.where(WorkflowDefinition.event_type == EventType(event_type))
    if is_active is not None:
        query = query.where(WorkflowDefinition.is_active == is_active)

    query = query.order_by(WorkflowDefinition.name)

    result = await db.execute(query)
    workflows = result.scalars().all()

    return [
        {
            "id": str(w.id),
            "name": w.name,
            "description": w.description,
            "event_type": w.event_type.value,
            "version": w.version,
            "is_active": w.is_active,
            "is_default": w.is_default,
            "max_retries": w.max_retries,
            "step_count": len(w.steps),
            "created_at": w.created_at.isoformat(),
        }
        for w in workflows
    ]


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get workflow with all steps."""
    result = await db.execute(
        select(WorkflowDefinition)
        .where(WorkflowDefinition.id == workflow_id)
        .options(selectinload(WorkflowDefinition.steps))
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return {
        "id": str(workflow.id),
        "name": workflow.name,
        "description": workflow.description,
        "event_type": workflow.event_type.value,
        "version": workflow.version,
        "is_active": workflow.is_active,
        "is_default": workflow.is_default,
        "max_retries": workflow.max_retries,
        "retry_delay_seconds": workflow.retry_delay_seconds,
        "timeout_seconds": workflow.timeout_seconds,
        "trigger_conditions": workflow.trigger_conditions,
        "created_at": workflow.created_at.isoformat(),
        "updated_at": workflow.updated_at.isoformat(),
        "steps": [
            {
                "id": str(s.id),
                "name": s.name,
                "description": s.description,
                "step_order": s.step_order,
                "action_type": s.action_type.value,
                "action_config": s.action_config,
                "requires_approval": s.requires_approval,
                "approval_timeout_hours": s.approval_timeout_hours,
                "is_optional": s.is_optional,
                "continue_on_failure": s.continue_on_failure,
            }
            for s in sorted(workflow.steps, key=lambda x: x.step_order)
        ],
    }


@router.post("/workflows")
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new workflow definition."""
    workflow = WorkflowDefinition(
        name=data.name,
        description=data.description,
        event_type=EventType(data.event_type),
        is_active=data.is_active,
        is_default=data.is_default,
        max_retries=data.max_retries,
        retry_delay_seconds=data.retry_delay_seconds,
        timeout_seconds=data.timeout_seconds,
        trigger_conditions=data.trigger_conditions,
    )

    # If setting as default, unset other defaults for this event type
    if data.is_default:
        await db.execute(
            update(WorkflowDefinition)
            .where(
                WorkflowDefinition.event_type == EventType(data.event_type),
                WorkflowDefinition.is_default == True,
            )
            .values(is_default=False)
        )

    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    return {"id": str(workflow.id), "name": workflow.name}


@router.patch("/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a workflow definition."""
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    update_data = data.model_dump(exclude_unset=True)

    if "is_default" in update_data and update_data["is_default"]:
        # Unset other defaults
        await db.execute(
            update(WorkflowDefinition)
            .where(
                WorkflowDefinition.event_type == workflow.event_type,
                WorkflowDefinition.id != workflow_id,
                WorkflowDefinition.is_default == True,
            )
            .values(is_default=False)
        )

    for key, value in update_data.items():
        setattr(workflow, key, value)

    workflow.updated_at = datetime.utcnow()
    await db.commit()

    return {"id": str(workflow.id), "updated": list(update_data.keys())}


@router.post("/workflows/{workflow_id}/steps")
async def add_workflow_step(
    workflow_id: UUID,
    data: WorkflowStepCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a step to a workflow."""
    # Verify workflow exists
    result = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == workflow_id)
    )
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    step = WorkflowStep(
        workflow_id=workflow_id,
        name=data.name,
        description=data.description,
        step_order=data.step_order,
        action_type=ActionType(data.action_type),
        action_config=data.action_config,
        requires_approval=data.requires_approval,
        approval_timeout_hours=data.approval_timeout_hours,
        auto_approve_after_timeout=data.auto_approve_after_timeout,
        is_optional=data.is_optional,
        continue_on_failure=data.continue_on_failure,
        max_retries=data.max_retries,
        condition=data.condition,
    )

    db.add(step)
    await db.commit()
    await db.refresh(step)

    return {"id": str(step.id), "name": step.name, "order": step.step_order}


@router.delete("/workflows/{workflow_id}/steps/{step_id}")
async def delete_workflow_step(
    workflow_id: UUID,
    step_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a workflow step."""
    result = await db.execute(
        select(WorkflowStep).where(
            WorkflowStep.id == step_id,
            WorkflowStep.workflow_id == workflow_id,
        )
    )
    step = result.scalar_one_or_none()

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    await db.delete(step)
    await db.commit()

    return {"deleted": str(step_id)}


# ============== Template Endpoints ==============

@router.get("/templates")
async def list_templates(
    channel: Optional[str] = None,
    event_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all notification templates."""
    query = select(NotificationTemplate)

    if channel:
        query = query.where(NotificationTemplate.channel == NotificationChannel(channel))
    if event_type:
        query = query.where(NotificationTemplate.event_type == EventType(event_type))

    query = query.order_by(NotificationTemplate.name)

    result = await db.execute(query)
    templates = result.scalars().all()

    return [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description,
            "event_type": t.event_type.value if t.event_type else None,
            "channel": t.channel.value,
            "subject_template": t.subject_template[:50] + "..." if len(t.subject_template) > 50 else t.subject_template,
            "is_active": t.is_active,
            "is_html": t.is_html,
        }
        for t in templates
    ]


@router.get("/templates/{template_id}")
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get template details."""
    result = await db.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
        "event_type": template.event_type.value if template.event_type else None,
        "channel": template.channel.value,
        "subject_template": template.subject_template,
        "body_template": template.body_template,
        "is_html": template.is_html,
        "html_template": template.html_template,
        "default_recipient_type": template.default_recipient_type.value if template.default_recipient_type else None,
        "is_active": template.is_active,
        "version": template.version,
        "available_variables": template.available_variables,
    }


@router.post("/templates")
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new notification template."""
    template = NotificationTemplate(
        name=data.name,
        description=data.description,
        event_type=EventType(data.event_type) if data.event_type else None,
        channel=NotificationChannel(data.channel),
        subject_template=data.subject_template,
        body_template=data.body_template,
        is_html=data.is_html,
        html_template=data.html_template,
        default_recipient_type=RecipientType(data.default_recipient_type) if data.default_recipient_type else None,
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return {"id": str(template.id), "name": template.name}


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a notification template."""
    result = await db.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    template.updated_at = datetime.utcnow()
    template.version += 1
    await db.commit()

    return {"id": str(template.id), "updated": list(update_data.keys())}


@router.post("/templates/{template_id}/preview")
async def preview_template(
    template_id: UUID,
    context: dict,
    db: AsyncSession = Depends(get_db),
):
    """Preview a template with sample context."""
    result = await db.execute(
        select(NotificationTemplate).where(NotificationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    from app.services.notification_service import TemplateRenderer
    renderer = TemplateRenderer()

    return {
        "subject": renderer.render(template.subject_template, context),
        "body": renderer.render(template.body_template, context),
    }


# ============== Integration Endpoints ==============

@router.get("/integrations")
async def list_integrations(
    system: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all integration configurations."""
    query = select(IntegrationConfig)

    if system:
        query = query.where(IntegrationConfig.system == IntegrationSystem(system))
    if is_active is not None:
        query = query.where(IntegrationConfig.is_active == is_active)

    query = query.order_by(IntegrationConfig.system, IntegrationConfig.name)

    result = await db.execute(query)
    integrations = result.scalars().all()

    return [
        {
            "id": str(i.id),
            "system": i.system.value,
            "name": i.name,
            "description": i.description,
            "base_url": i.base_url,
            "is_active": i.is_active,
            "is_default": i.is_default,
            "health_status": i.health_status.value,
            "last_health_check": i.last_health_check.isoformat() if i.last_health_check else None,
            "success_rate": i.success_rate,
        }
        for i in integrations
    ]


@router.get("/integrations/{integration_id}")
async def get_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get integration details (credentials redacted)."""
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    return {
        "id": str(integration.id),
        "system": integration.system.value,
        "name": integration.name,
        "description": integration.description,
        "base_url": integration.base_url,
        "auth_type": integration.auth_type,
        "config": integration.config,
        "is_active": integration.is_active,
        "is_default": integration.is_default,
        "health_status": integration.health_status.value,
        "last_health_check": integration.last_health_check.isoformat() if integration.last_health_check else None,
        "last_health_message": integration.last_health_message,
        "total_requests": integration.total_requests,
        "failed_requests": integration.failed_requests,
        "success_rate": integration.success_rate,
    }


@router.post("/integrations")
async def create_integration(
    data: IntegrationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new integration configuration."""
    integration = IntegrationConfig(
        system=IntegrationSystem(data.system),
        name=data.name,
        description=data.description,
        base_url=data.base_url,
        auth_type=data.auth_type,
        credentials=data.credentials,
        config=data.config,
        is_active=data.is_active,
        is_default=data.is_default,
    )

    # If setting as default, unset other defaults for this system
    if data.is_default:
        await db.execute(
            update(IntegrationConfig)
            .where(
                IntegrationConfig.system == IntegrationSystem(data.system),
                IntegrationConfig.is_default == True,
            )
            .values(is_default=False)
        )

    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    return {"id": str(integration.id), "name": integration.name}


@router.patch("/integrations/{integration_id}")
async def update_integration(
    integration_id: UUID,
    data: IntegrationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an integration configuration."""
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    update_data = data.model_dump(exclude_unset=True)

    if "is_default" in update_data and update_data["is_default"]:
        # Unset other defaults
        await db.execute(
            update(IntegrationConfig)
            .where(
                IntegrationConfig.system == integration.system,
                IntegrationConfig.id != integration_id,
                IntegrationConfig.is_default == True,
            )
            .values(is_default=False)
        )

    for key, value in update_data.items():
        setattr(integration, key, value)

    integration.updated_at = datetime.utcnow()
    await db.commit()

    return {"id": str(integration.id), "updated": list(update_data.keys())}


@router.post("/integrations/{integration_id}/test")
async def test_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Test an integration connection."""
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Test based on system type
    healthy = False
    message = ""

    try:
        if integration.system == IntegrationSystem.servicenow:
            from app.integrations.servicenow import ServiceNowClient
            async with ServiceNowClient(integration, db) as client:
                healthy = await client.health_check()
                message = "Connection successful" if healthy else "Health check failed"

        elif integration.system == IntegrationSystem.salesforce:
            from app.integrations.salesforce import SalesforceClient
            async with SalesforceClient(integration, db) as client:
                healthy = await client.health_check()
                message = "Connection successful" if healthy else "Health check failed"

        elif integration.system == IntegrationSystem.sendgrid:
            from app.integrations.email import SendGridClient
            async with SendGridClient(integration, db) as client:
                healthy = await client.health_check()
                message = "Connection successful" if healthy else "Health check failed"

        elif integration.system == IntegrationSystem.teams:
            from app.integrations.teams import TeamsClient
            client = TeamsClient(integration, db)
            healthy = await client.health_check()
            message = "Connection successful" if healthy else "Health check failed"

        else:
            message = "Test not implemented for this system type"

    except Exception as e:
        message = str(e)[:500]

    # Update health status
    integration.health_status = IntegrationStatus.healthy if healthy else IntegrationStatus.unhealthy
    integration.last_health_check = datetime.utcnow()
    integration.last_health_message = message
    await db.commit()

    return {
        "healthy": healthy,
        "message": message,
        "checked_at": integration.last_health_check.isoformat(),
    }


# ============== Approver Endpoints ==============

@router.get("/approvers")
async def list_approvers(
    workflow_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all approvers."""
    query = select(Approver).options(
        selectinload(Approver.user),
        selectinload(Approver.workflow),
    )

    if workflow_id:
        query = query.where(Approver.workflow_id == workflow_id)

    result = await db.execute(query)
    approvers = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "workflow_id": str(a.workflow_id),
            "workflow_name": a.workflow.name if a.workflow else None,
            "user_id": str(a.user_id),
            "user_email": a.user.email if a.user else None,
            "is_primary": a.is_primary,
            "can_delegate": a.can_delegate,
            "approval_order": a.approval_order,
            "is_active": a.is_active,
            "out_of_office": a.out_of_office,
        }
        for a in approvers
    ]


@router.post("/approvers")
async def add_approver(
    data: ApproverCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add an approver to a workflow."""
    # Verify workflow and user exist
    workflow = await db.execute(
        select(WorkflowDefinition).where(WorkflowDefinition.id == data.workflow_id)
    )
    if not workflow.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    user = await db.execute(
        select(User).where(User.id == data.user_id)
    )
    if not user.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    approver = Approver(
        workflow_id=data.workflow_id,
        user_id=data.user_id,
        is_primary=data.is_primary,
        can_delegate=data.can_delegate,
        approval_order=data.approval_order,
        notify_email=data.notify_email,
        notify_slack=data.notify_slack,
    )

    db.add(approver)
    await db.commit()
    await db.refresh(approver)

    return {"id": str(approver.id)}


@router.delete("/approvers/{approver_id}")
async def remove_approver(
    approver_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove an approver."""
    result = await db.execute(
        select(Approver).where(Approver.id == approver_id)
    )
    approver = result.scalar_one_or_none()

    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")

    await db.delete(approver)
    await db.commit()

    return {"deleted": str(approver_id)}


# ============== Teams Notification Test ==============

class TeamsTestNotification(BaseModel):
    """Test notification payload for Teams."""
    title: str = "CLM Test Notification"
    message: str = "This is a test notification from the Contract Lifecycle Management platform."
    severity: str = "info"  # info, warning, error, success


@router.post("/integrations/{integration_id}/teams/test-notification")
async def send_teams_test_notification(
    integration_id: UUID,
    data: TeamsTestNotification = TeamsTestNotification(),
    db: AsyncSession = Depends(get_db),
):
    """Send a test notification to Teams via Power Automate.

    Use this endpoint to verify your Teams integration is working correctly.
    """
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if integration.system != IntegrationSystem.teams:
        raise HTTPException(
            status_code=400,
            detail=f"Integration is not a Teams integration (found: {integration.system.value})"
        )

    try:
        from app.integrations.teams import TeamsClient
        client = TeamsClient(integration, db)

        result = await client.send_notification(
            title=data.title,
            message=data.message,
            severity=data.severity,
            details={
                "Integration": integration.name,
                "Test": "This is a test notification",
                "Source": "CLM Admin API",
            },
        )

        # Update last used
        integration.last_used_at = datetime.utcnow()
        integration.total_requests += 1
        await db.commit()

        return {
            "success": result["status"] == "sent",
            "message": "Test notification sent successfully" if result["status"] == "sent" else "Failed to send notification",
            "details": result,
        }

    except Exception as e:
        integration.failed_requests += 1
        await db.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send notification: {str(e)}"
        )
