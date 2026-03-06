"""API endpoints for configurable notification rules.

Provides:
- CRUD operations for notification rules
- Rule templates for quick setup
- Test notifications
"""

from datetime import datetime, time
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, CurrentUser, CurrentTenantId
from app.models.notification_rule import NotificationRule, RuleEventType


router = APIRouter(prefix="/api/notification-rules", tags=["notification-rules"])


# ===== Request/Response Models =====

class NotificationRuleCreate(BaseModel):
    """Create a notification rule."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: RuleEventType
    days_before: int = Field(default=7, ge=0, le=365)
    repeat_interval_days: Optional[int] = Field(default=None, ge=1, le=30)
    max_repeats: int = Field(default=3, ge=0, le=10)
    channels: list[str] = Field(default=["email"])
    notify_contract_owner: bool = True
    notify_admin: bool = False
    additional_recipients: Optional[list[str]] = None
    contract_types: Optional[list[str]] = None
    min_contract_value: Optional[float] = None
    risk_levels: Optional[list[str]] = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    respect_business_hours: bool = False
    business_hours_start: Optional[str] = None  # HH:MM format
    business_hours_end: Optional[str] = None
    email_template: Optional[str] = None


class NotificationRuleUpdate(BaseModel):
    """Update a notification rule."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    days_before: Optional[int] = Field(default=None, ge=0, le=365)
    repeat_interval_days: Optional[int] = Field(default=None, ge=1, le=30)
    max_repeats: Optional[int] = Field(default=None, ge=0, le=10)
    channels: Optional[list[str]] = None
    notify_contract_owner: Optional[bool] = None
    notify_admin: Optional[bool] = None
    additional_recipients: Optional[list[str]] = None
    contract_types: Optional[list[str]] = None
    min_contract_value: Optional[float] = None
    risk_levels: Optional[list[str]] = None
    priority: Optional[str] = None
    respect_business_hours: Optional[bool] = None
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None
    email_template: Optional[str] = None


class NotificationRuleResponse(BaseModel):
    """Notification rule response."""

    id: str
    name: str
    description: Optional[str]
    is_active: bool
    event_type: str
    days_before: int
    repeat_interval_days: Optional[int]
    max_repeats: int
    channels: list[str]
    notify_contract_owner: bool
    notify_admin: bool
    additional_recipients: Optional[list[str]]
    contract_types: Optional[list[str]]
    min_contract_value: Optional[float]
    risk_levels: Optional[list[str]]
    priority: str
    respect_business_hours: bool
    business_hours_start: Optional[str]
    business_hours_end: Optional[str]
    email_template: Optional[str]
    last_triggered: Optional[datetime]
    trigger_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RuleTemplate(BaseModel):
    """Pre-defined rule template."""

    name: str
    description: str
    event_type: str
    days_before: int
    channels: list[str]
    priority: str


# ===== Pre-defined Templates =====

RULE_TEMPLATES = [
    RuleTemplate(
        name="Contract Expiration Warning",
        description="Notify 30 days before contract expires",
        event_type="contract_expiration",
        days_before=30,
        channels=["email", "in_app"],
        priority="high",
    ),
    RuleTemplate(
        name="Notice Deadline Alert",
        description="Notify 14 days before notice deadline",
        event_type="notice_deadline",
        days_before=14,
        channels=["email"],
        priority="critical",
    ),
    RuleTemplate(
        name="Obligation Due Reminder",
        description="Notify 7 days before obligation deadline",
        event_type="obligation_due",
        days_before=7,
        channels=["email", "in_app"],
        priority="normal",
    ),
    RuleTemplate(
        name="SLA Breach Alert",
        description="Immediate notification on SLA breach",
        event_type="sla_breach",
        days_before=0,
        channels=["email", "in_app"],
        priority="critical",
    ),
    RuleTemplate(
        name="SLA Warning",
        description="Notify when SLA is at risk",
        event_type="sla_warning",
        days_before=0,
        channels=["email"],
        priority="high",
    ),
    RuleTemplate(
        name="Renewal Reminder",
        description="Notify 60 days before auto-renewal",
        event_type="renewal_reminder",
        days_before=60,
        channels=["email", "in_app"],
        priority="normal",
    ),
    RuleTemplate(
        name="Compliance Overdue Alert",
        description="Immediate notification for overdue compliance",
        event_type="compliance_overdue",
        days_before=0,
        channels=["email", "in_app"],
        priority="critical",
    ),
]


# ===== Helper Functions =====

def rule_to_response(rule: NotificationRule) -> NotificationRuleResponse:
    """Convert rule model to response."""
    return NotificationRuleResponse(
        id=str(rule.id),
        name=rule.name,
        description=rule.description,
        is_active=rule.is_active,
        event_type=rule.event_type.value,
        days_before=rule.days_before,
        repeat_interval_days=rule.repeat_interval_days,
        max_repeats=rule.max_repeats,
        channels=rule.channels if isinstance(rule.channels, list) else ["email"],
        notify_contract_owner=rule.notify_contract_owner,
        notify_admin=rule.notify_admin,
        additional_recipients=rule.additional_recipients,
        contract_types=rule.contract_types,
        min_contract_value=rule.min_contract_value,
        risk_levels=rule.risk_levels,
        priority=rule.priority,
        respect_business_hours=rule.respect_business_hours,
        business_hours_start=rule.business_hours_start.strftime("%H:%M") if rule.business_hours_start else None,
        business_hours_end=rule.business_hours_end.strftime("%H:%M") if rule.business_hours_end else None,
        email_template=rule.email_template,
        last_triggered=rule.last_triggered,
        trigger_count=rule.trigger_count,
        created_at=rule.created_at,
    )


def parse_time(time_str: Optional[str]) -> Optional[time]:
    """Parse HH:MM string to time object."""
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


# ===== Endpoints =====

@router.get("/", response_model=list[NotificationRuleResponse])
async def list_rules(
    event_type: Optional[RuleEventType] = None,
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """List notification rules for the tenant."""
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant context required")

    query = select(NotificationRule).where(NotificationRule.tenant_id == tenant_id)

    if active_only:
        query = query.where(NotificationRule.is_active == True)

    if event_type:
        query = query.where(NotificationRule.event_type == event_type)

    query = query.order_by(NotificationRule.created_at.desc())

    result = await db.execute(query)
    rules = result.scalars().all()

    return [rule_to_response(rule) for rule in rules]


@router.get("/templates", response_model=list[RuleTemplate])
async def get_templates():
    """Get pre-defined rule templates."""
    return RULE_TEMPLATES


@router.post("/", response_model=NotificationRuleResponse)
async def create_rule(
    data: NotificationRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Create a notification rule."""
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant context required")

    rule = NotificationRule(
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        event_type=data.event_type,
        days_before=data.days_before,
        repeat_interval_days=data.repeat_interval_days,
        max_repeats=data.max_repeats,
        channels=data.channels,
        notify_contract_owner=data.notify_contract_owner,
        notify_admin=data.notify_admin,
        additional_recipients=data.additional_recipients,
        contract_types=data.contract_types,
        min_contract_value=data.min_contract_value,
        risk_levels=data.risk_levels,
        priority=data.priority,
        respect_business_hours=data.respect_business_hours,
        business_hours_start=parse_time(data.business_hours_start),
        business_hours_end=parse_time(data.business_hours_end),
        email_template=data.email_template,
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return rule_to_response(rule)


@router.post("/from-template/{template_index}", response_model=NotificationRuleResponse)
async def create_from_template(
    template_index: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Create a notification rule from a template."""
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant context required")

    if template_index < 0 or template_index >= len(RULE_TEMPLATES):
        raise HTTPException(status_code=400, detail="Invalid template index")

    template = RULE_TEMPLATES[template_index]

    rule = NotificationRule(
        tenant_id=tenant_id,
        name=template.name,
        description=template.description,
        event_type=RuleEventType(template.event_type),
        days_before=template.days_before,
        channels=template.channels,
        priority=template.priority,
        notify_contract_owner=True,
        notify_admin=template.priority == "critical",
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return rule_to_response(rule)


@router.get("/{rule_id}", response_model=NotificationRuleResponse)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Get a notification rule by ID."""
    query = select(NotificationRule).where(NotificationRule.id == rule_id)

    if tenant_id is not None:
        query = query.where(NotificationRule.tenant_id == tenant_id)

    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return rule_to_response(rule)


@router.put("/{rule_id}", response_model=NotificationRuleResponse)
async def update_rule(
    rule_id: UUID,
    data: NotificationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Update a notification rule."""
    query = select(NotificationRule).where(NotificationRule.id == rule_id)

    if tenant_id is not None:
        query = query.where(NotificationRule.tenant_id == tenant_id)

    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Update fields if provided
    if data.name is not None:
        rule.name = data.name
    if data.description is not None:
        rule.description = data.description
    if data.is_active is not None:
        rule.is_active = data.is_active
    if data.days_before is not None:
        rule.days_before = data.days_before
    if data.repeat_interval_days is not None:
        rule.repeat_interval_days = data.repeat_interval_days
    if data.max_repeats is not None:
        rule.max_repeats = data.max_repeats
    if data.channels is not None:
        rule.channels = data.channels
    if data.notify_contract_owner is not None:
        rule.notify_contract_owner = data.notify_contract_owner
    if data.notify_admin is not None:
        rule.notify_admin = data.notify_admin
    if data.additional_recipients is not None:
        rule.additional_recipients = data.additional_recipients
    if data.contract_types is not None:
        rule.contract_types = data.contract_types
    if data.min_contract_value is not None:
        rule.min_contract_value = data.min_contract_value
    if data.risk_levels is not None:
        rule.risk_levels = data.risk_levels
    if data.priority is not None:
        rule.priority = data.priority
    if data.respect_business_hours is not None:
        rule.respect_business_hours = data.respect_business_hours
    if data.business_hours_start is not None:
        rule.business_hours_start = parse_time(data.business_hours_start)
    if data.business_hours_end is not None:
        rule.business_hours_end = parse_time(data.business_hours_end)
    if data.email_template is not None:
        rule.email_template = data.email_template

    await db.commit()
    await db.refresh(rule)

    return rule_to_response(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Delete a notification rule."""
    query = select(NotificationRule).where(NotificationRule.id == rule_id)

    if tenant_id is not None:
        query = query.where(NotificationRule.tenant_id == tenant_id)

    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()

    return {"success": True, "message": "Rule deleted"}


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Toggle a notification rule's active status."""
    query = select(NotificationRule).where(NotificationRule.id == rule_id)

    if tenant_id is not None:
        query = query.where(NotificationRule.tenant_id == tenant_id)

    result = await db.execute(query)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    await db.commit()

    return {
        "success": True,
        "rule_id": str(rule.id),
        "is_active": rule.is_active,
    }


@router.get("/summary/stats")
async def get_rule_stats(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Get notification rule statistics."""
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Tenant context required")

    # Total rules
    total_result = await db.execute(
        select(func.count(NotificationRule.id)).where(
            NotificationRule.tenant_id == tenant_id
        )
    )
    total = total_result.scalar() or 0

    # Active rules
    active_result = await db.execute(
        select(func.count(NotificationRule.id)).where(
            NotificationRule.tenant_id == tenant_id,
            NotificationRule.is_active == True
        )
    )
    active = active_result.scalar() or 0

    # By event type
    by_event_type = {}
    for event_type in RuleEventType:
        result = await db.execute(
            select(func.count(NotificationRule.id)).where(
                NotificationRule.tenant_id == tenant_id,
                NotificationRule.event_type == event_type,
                NotificationRule.is_active == True
            )
        )
        count = result.scalar() or 0
        if count > 0:
            by_event_type[event_type.value] = count

    # Total triggers
    triggers_result = await db.execute(
        select(func.sum(NotificationRule.trigger_count)).where(
            NotificationRule.tenant_id == tenant_id
        )
    )
    total_triggers = triggers_result.scalar() or 0

    return {
        "total_rules": total,
        "active_rules": active,
        "inactive_rules": total - active,
        "by_event_type": by_event_type,
        "total_triggers": total_triggers,
    }
