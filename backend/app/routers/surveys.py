"""API endpoints for Survey management (Evaluetor features)."""

from uuid import UUID, uuid4
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, require_role, CurrentTenantId
from app.core.tenant import apply_tenant_filter
from app.models import (
    User,
    SurveyTemplate,
    SurveyQuestion,
    SurveyInstance,
    SurveyResponse,
    SurveyStatus,
    BusinessRelationship,
    ExternalAccessToken,
    TokenType,
    PerceptionScore,
    KPI,
)
from app.schemas.survey import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse,
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    InstanceCreate,
    InstanceUpdate,
    InstanceResponse,
    InstanceListResponse,
    ResponseCreate,
    ResponseResponse,
    ResponseListResponse,
    ExternalSurveyContext,
)

router = APIRouter(prefix="/api/surveys", tags=["Surveys"])


async def _verify_instance_tenant(
    db: AsyncSession, instance_id: UUID, tenant_id: UUID | None,
) -> SurveyInstance | None:
    """Verify a survey instance belongs to the current tenant via its relationship chain."""
    from app.models import Organization

    query = (
        select(SurveyInstance)
        .where(SurveyInstance.id == instance_id)
        .options(
            selectinload(SurveyInstance.template),
            selectinload(SurveyInstance.relationship),
        )
    )
    if tenant_id is not None:
        query = query.join(
            BusinessRelationship, SurveyInstance.relationship_id == BusinessRelationship.id
        ).where(BusinessRelationship.tenant_id == tenant_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# ===== Templates =====

@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    active_only: bool = Query(True),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List survey templates."""
    query = select(SurveyTemplate)

    if active_only:
        query = query.where(SurveyTemplate.is_active == True)

    if search:
        query = query.where(SurveyTemplate.name.ilike(f"%{search}%"))

    query = query.order_by(SurveyTemplate.name)

    result = await db.execute(query)
    templates = result.scalars().all()

    # Get question counts
    items = []
    for t in templates:
        count_result = await db.execute(
            select(func.count()).where(
                SurveyQuestion.template_id == t.id,
                SurveyQuestion.is_active == True,
            )
        )
        question_count = count_result.scalar() or 0

        items.append(_template_to_response(t, question_count=question_count))

    return TemplateListResponse(items=items, total=len(items))


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Create a new survey template."""
    template = SurveyTemplate(
        name=data.name,
        description=data.description,
        frequency=data.frequency,
        introduction_text=data.introduction_text,
        closing_text=data.closing_text,
        allow_anonymous=data.allow_anonymous,
        require_all_questions=data.require_all_questions,
    )
    db.add(template)
    await db.flush()

    # Add questions if provided
    if data.questions:
        for i, q_data in enumerate(data.questions):
            question = SurveyQuestion(
                template_id=template.id,
                text=q_data.text,
                help_text=q_data.help_text,
                question_type=q_data.question_type,
                options=q_data.options,
                rating_min_label=q_data.rating_min_label,
                rating_max_label=q_data.rating_max_label,
                kpi_id=q_data.kpi_id,
                sequence=q_data.sequence if q_data.sequence > 0 else i + 1,
                is_required=q_data.is_required,
            )
            db.add(question)

    await db.commit()
    await db.refresh(template)

    # Reload with questions
    result = await db.execute(
        select(SurveyTemplate)
        .where(SurveyTemplate.id == template.id)
        .options(selectinload(SurveyTemplate.questions))
    )
    template = result.scalar_one()

    return _template_to_response(template, include_questions=True)


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a template by ID."""
    result = await db.execute(
        select(SurveyTemplate)
        .where(SurveyTemplate.id == template_id)
        .options(selectinload(SurveyTemplate.questions))
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return _template_to_response(template, include_questions=True)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Update a template."""
    template = await db.get(SurveyTemplate, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    template.version += 1
    await db.commit()
    await db.refresh(template)

    return _template_to_response(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Soft delete a template."""
    template = await db.get(SurveyTemplate, template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    template.is_active = False
    await db.commit()


# ===== Questions =====

@router.post("/templates/{template_id}/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def add_question(
    template_id: UUID,
    data: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Add a question to a template."""
    template = await db.get(SurveyTemplate, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Get max sequence
    max_seq_result = await db.execute(
        select(func.max(SurveyQuestion.sequence)).where(
            SurveyQuestion.template_id == template_id
        )
    )
    max_seq = max_seq_result.scalar() or 0

    question = SurveyQuestion(
        template_id=template_id,
        text=data.text,
        help_text=data.help_text,
        question_type=data.question_type,
        options=data.options,
        rating_min_label=data.rating_min_label,
        rating_max_label=data.rating_max_label,
        kpi_id=data.kpi_id,
        sequence=data.sequence if data.sequence > 0 else max_seq + 1,
        is_required=data.is_required,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    return _question_to_response(question)


@router.put("/templates/{template_id}/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    template_id: UUID,
    question_id: UUID,
    data: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Update a question."""
    result = await db.execute(
        select(SurveyQuestion).where(
            SurveyQuestion.id == question_id,
            SurveyQuestion.template_id == template_id,
        )
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(question, field, value)

    await db.commit()
    await db.refresh(question)

    return _question_to_response(question)


@router.delete("/templates/{template_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    template_id: UUID,
    question_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Soft delete a question."""
    result = await db.execute(
        select(SurveyQuestion).where(
            SurveyQuestion.id == question_id,
            SurveyQuestion.template_id == template_id,
        )
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )

    question.is_active = False
    await db.commit()


# ===== Instances =====

@router.get("/instances", response_model=InstanceListResponse)
async def list_instances(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    relationship_id: Optional[UUID] = None,
    template_id: Optional[UUID] = None,
    status_filter: Optional[SurveyStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: CurrentTenantId = None,
):
    """List survey instances."""
    from app.models import Organization

    query = select(SurveyInstance).options(
        selectinload(SurveyInstance.template),
        selectinload(SurveyInstance.relationship),
    )

    # Apply tenant filter via relationship -> organization
    if tenant_id is not None:
        query = query.join(
            BusinessRelationship, SurveyInstance.relationship_id == BusinessRelationship.id
        ).join(
            Organization, BusinessRelationship.org_a_id == Organization.id
        ).where(Organization.tenant_id == tenant_id)

    if relationship_id:
        query = query.where(SurveyInstance.relationship_id == relationship_id)

    if template_id:
        query = query.where(SurveyInstance.template_id == template_id)

    if status_filter:
        query = query.where(SurveyInstance.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(SurveyInstance.created_at.desc())

    result = await db.execute(query)
    instances = result.scalars().all()

    return InstanceListResponse(
        items=[_instance_to_response(i) for i in instances],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/instances", response_model=InstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_instance(
    data: InstanceCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Create a new survey instance."""
    # Validate template exists
    template = await db.get(SurveyTemplate, data.template_id)
    if not template or not template.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template not found or inactive",
        )

    # Validate relationship exists and belongs to tenant
    rel_query = select(BusinessRelationship).where(BusinessRelationship.id == data.relationship_id)
    rel_query = apply_tenant_filter(rel_query, tenant_id, BusinessRelationship)
    rel_result = await db.execute(rel_query)
    relationship = rel_result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Relationship not found",
        )

    instance = SurveyInstance(
        template_id=data.template_id,
        relationship_id=data.relationship_id,
        period=data.period,
        scheduled_send_date=data.scheduled_send_date,
        due_date=data.due_date,
        target_respondent_count=data.target_respondent_count,
        notes=data.notes,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    # Reload with joins
    result = await db.execute(
        select(SurveyInstance)
        .where(SurveyInstance.id == instance.id)
        .options(
            selectinload(SurveyInstance.template),
            selectinload(SurveyInstance.relationship),
        )
    )
    instance = result.scalar_one()

    return _instance_to_response(instance)


@router.get("/instances/{instance_id}", response_model=InstanceResponse)
async def get_instance(
    instance_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a survey instance by ID."""
    instance = await _verify_instance_tenant(db, instance_id, tenant_id)

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey instance not found",
        )

    return _instance_to_response(instance)


@router.put("/instances/{instance_id}", response_model=InstanceResponse)
async def update_instance(
    instance_id: UUID,
    data: InstanceUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Update a survey instance."""
    instance = await _verify_instance_tenant(db, instance_id, tenant_id)

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey instance not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Handle status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == SurveyStatus.IN_PROGRESS and instance.status == SurveyStatus.DRAFT:
            instance.sent_at = datetime.utcnow()
        elif new_status == SurveyStatus.CLOSED and instance.status == SurveyStatus.IN_PROGRESS:
            instance.closed_at = datetime.utcnow()

    for field, value in update_data.items():
        setattr(instance, field, value)

    await db.commit()
    await db.refresh(instance)

    return _instance_to_response(instance)


@router.post("/instances/{instance_id}/send", response_model=InstanceResponse)
async def send_survey(
    instance_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Send a survey (transition from DRAFT to IN_PROGRESS)."""
    instance = await _verify_instance_tenant(db, instance_id, tenant_id)

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey instance not found",
        )

    if instance.status != SurveyStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot send survey in {instance.status.value} status",
        )

    instance.status = SurveyStatus.IN_PROGRESS
    instance.sent_at = datetime.utcnow()
    await db.commit()
    await db.refresh(instance)

    return _instance_to_response(instance)


@router.post("/instances/{instance_id}/close", response_model=InstanceResponse)
async def close_survey(
    instance_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Close a survey (transition from IN_PROGRESS to CLOSED)."""
    instance = await _verify_instance_tenant(db, instance_id, tenant_id)

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey instance not found",
        )

    if instance.status != SurveyStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot close survey in {instance.status.value} status",
        )

    instance.status = SurveyStatus.CLOSED
    instance.closed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(instance)

    return _instance_to_response(instance)


# ===== Responses =====

@router.get("/instances/{instance_id}/responses", response_model=ResponseListResponse)
async def list_responses(
    instance_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List responses for a survey instance."""
    # Verify instance belongs to tenant
    instance = await _verify_instance_tenant(db, instance_id, tenant_id)
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey instance not found")

    result = await db.execute(
        select(SurveyResponse)
        .where(SurveyResponse.survey_instance_id == instance_id)
        .order_by(SurveyResponse.submitted_at.desc())
    )
    responses = result.scalars().all()

    return ResponseListResponse(
        items=[_response_to_response(r) for r in responses],
        total=len(responses),
    )


@router.get("/instances/{instance_id}/responses/{response_id}", response_model=ResponseResponse)
async def get_response(
    instance_id: UUID,
    response_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific survey response."""
    # Verify instance belongs to tenant
    instance = await _verify_instance_tenant(db, instance_id, tenant_id)
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey instance not found")

    result = await db.execute(
        select(SurveyResponse).where(
            SurveyResponse.id == response_id,
            SurveyResponse.survey_instance_id == instance_id,
        )
    )
    response = result.scalar_one_or_none()

    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found",
        )

    return _response_to_response(response)


# ===== External Survey Access =====

@router.post("/instances/{instance_id}/generate-token")
async def generate_survey_token(
    instance_id: UUID,
    org_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Generate an external access token for survey completion."""
    instance = await _verify_instance_tenant(db, instance_id, tenant_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey instance not found",
        )

    if instance.status != SurveyStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey is not active",
        )

    # Create access token
    token = ExternalAccessToken.create_token(
        token_type=TokenType.SURVEY,
        resource_id=instance_id,
        organization_id=org_id,
        expires_in_days=30,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)

    return {
        "token": token.token,
        "expires_at": token.expires_at.isoformat(),
        "survey_url": f"/external/surveys/{token.token}",
    }


@router.get("/external/{token}", response_model=ExternalSurveyContext)
async def get_external_survey(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Get survey context for external respondent (no auth required)."""
    result = await db.execute(
        select(ExternalAccessToken).where(
            ExternalAccessToken.token == token,
            ExternalAccessToken.token_type == TokenType.SURVEY,
        )
    )
    access_token = result.scalar_one_or_none()

    if not access_token or not access_token.is_valid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired survey link",
        )

    # Get survey instance with template
    instance_result = await db.execute(
        select(SurveyInstance)
        .where(SurveyInstance.id == access_token.resource_id)
        .options(
            selectinload(SurveyInstance.template).selectinload(SurveyTemplate.questions),
            selectinload(SurveyInstance.relationship),
        )
    )
    instance = instance_result.scalar_one_or_none()

    if not instance or instance.status != SurveyStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey is not available",
        )

    # Get organization name
    from app.models import Organization
    org = await db.get(Organization, access_token.organization_id)

    return ExternalSurveyContext(
        instance_id=instance.id,
        template_name=instance.template.name,
        relationship_name=instance.relationship.name if instance.relationship else None,
        organization_name=org.name if org else "Unknown Organization",
        period=instance.period,
        introduction_text=instance.template.introduction_text,
        questions=[_question_to_response(q) for q in instance.template.questions if q.is_active],
        allow_anonymous=instance.template.allow_anonymous,
        due_date=instance.due_date,
    )


@router.post("/external/{token}", response_model=ResponseResponse)
async def submit_external_survey(
    token: str,
    data: ResponseCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit survey response from external respondent (no auth required)."""
    result = await db.execute(
        select(ExternalAccessToken).where(
            ExternalAccessToken.token == token,
            ExternalAccessToken.token_type == TokenType.SURVEY,
        )
    )
    access_token = result.scalar_one_or_none()

    if not access_token or not access_token.is_valid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired survey link",
        )

    # Get survey instance
    instance = await db.get(SurveyInstance, access_token.resource_id)
    if not instance or instance.status != SurveyStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey is not accepting responses",
        )

    # Create response
    response = SurveyResponse(
        survey_instance_id=instance.id,
        respondent_org_id=access_token.organization_id,
        respondent_email=data.respondent_email,
        respondent_name=data.respondent_name,
        is_anonymous=data.is_anonymous,
        answers=data.answers,
        is_complete=True,
        submitted_at=datetime.utcnow(),
    )
    db.add(response)

    # Update instance count
    instance.actual_respondent_count += 1

    # Update access token usage
    access_token.used_at = datetime.utcnow()
    access_token.use_count += 1

    await db.commit()
    await db.refresh(response)

    # Process KPI-linked questions to create perception scores
    await _process_survey_to_perception_scores(db, instance, response)

    return _response_to_response(response)


# ===== Helper Functions =====

def _template_to_response(
    template: SurveyTemplate,
    include_questions: bool = False,
    question_count: Optional[int] = None,
) -> TemplateResponse:
    """Convert template model to response schema."""
    response = TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        frequency=template.frequency,
        introduction_text=template.introduction_text,
        closing_text=template.closing_text,
        allow_anonymous=template.allow_anonymous,
        require_all_questions=template.require_all_questions,
        is_active=template.is_active,
        version=template.version,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )

    if include_questions and hasattr(template, 'questions'):
        response.questions = [
            _question_to_response(q)
            for q in sorted(template.questions, key=lambda x: x.sequence)
            if q.is_active
        ]
        response.question_count = len(response.questions)
    elif question_count is not None:
        response.question_count = question_count

    return response


def _question_to_response(question: SurveyQuestion) -> QuestionResponse:
    """Convert question model to response schema."""
    return QuestionResponse(
        id=question.id,
        template_id=question.template_id,
        text=question.text,
        help_text=question.help_text,
        question_type=question.question_type,
        options=question.options,
        rating_min_label=question.rating_min_label,
        rating_max_label=question.rating_max_label,
        kpi_id=question.kpi_id,
        sequence=question.sequence,
        is_required=question.is_required,
        is_active=question.is_active,
        created_at=question.created_at,
    )


def _instance_to_response(instance: SurveyInstance) -> InstanceResponse:
    """Convert instance model to response schema."""
    response_rate = None
    if instance.target_respondent_count and instance.target_respondent_count > 0:
        response_rate = instance.actual_respondent_count / instance.target_respondent_count

    return InstanceResponse(
        id=instance.id,
        template_id=instance.template_id,
        relationship_id=instance.relationship_id,
        period=instance.period,
        status=instance.status,
        scheduled_send_date=instance.scheduled_send_date,
        sent_at=instance.sent_at,
        due_date=instance.due_date,
        closed_at=instance.closed_at,
        target_respondent_count=instance.target_respondent_count,
        actual_respondent_count=instance.actual_respondent_count,
        response_rate=response_rate,
        notes=instance.notes,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
        template_name=instance.template.name if instance.template else None,
        relationship_name=instance.relationship.name if instance.relationship else None,
    )


def _response_to_response(response: SurveyResponse) -> ResponseResponse:
    """Convert survey response model to response schema."""
    return ResponseResponse(
        id=response.id,
        survey_instance_id=response.survey_instance_id,
        respondent_email=response.respondent_email,
        respondent_name=response.respondent_name,
        respondent_org_id=response.respondent_org_id,
        is_anonymous=response.is_anonymous,
        answers=response.answers,
        completion_time_seconds=response.completion_time_seconds,
        is_complete=response.is_complete,
        submitted_at=response.submitted_at,
        created_at=response.created_at,
    )


async def _process_survey_to_perception_scores(
    db: AsyncSession,
    instance: SurveyInstance,
    response: SurveyResponse,
):
    """Process survey answers to create perception scores for KPI-linked questions."""
    # Get template questions with KPI links
    result = await db.execute(
        select(SurveyQuestion).where(
            SurveyQuestion.template_id == instance.template_id,
            SurveyQuestion.kpi_id.isnot(None),
            SurveyQuestion.is_active == True,
        )
    )
    kpi_questions = result.scalars().all()

    for question in kpi_questions:
        question_id_str = str(question.id)
        if question_id_str in response.answers:
            answer = response.answers[question_id_str]

            # Only process numeric answers (ratings)
            try:
                score_value = float(answer)
            except (ValueError, TypeError):
                continue

            # Create perception score
            perception_score = PerceptionScore(
                kpi_id=question.kpi_id,
                relationship_id=instance.relationship_id,
                respondent_org_id=response.respondent_org_id,
                score_value=score_value,
                period=instance.period,
                survey_response_id=response.id,
                is_external=True,
            )
            db.add(perception_score)

    await db.commit()
