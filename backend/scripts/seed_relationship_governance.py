#!/usr/bin/env python3
"""
Seed script to populate relationship governance data (Evaluetor features).
Run with: python -m scripts.seed_relationship_governance
"""

import asyncio
import random
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import User
from app.models.organization import Organization, OrganizationType, OrganizationSize
from app.models.relationship import (
    BusinessRelationship,
    RelationshipTeam,
    RelationshipType,
    RelationshipStatus,
    GovernanceTier,
    TeamRole,
)
from app.models.kpi import (
    KPI,
    PerceptionScore,
    PerceptionGap,
    KPIMeasurementType,
    KPICategory,
)
from app.models.improvement import (
    ImprovementPoint,
    ImprovementAction,
    ImprovementPriority,
    ImprovementStatus,
    ImprovementSource,
    ActionStatus,
)
from app.models.survey import (
    SurveyTemplate,
    SurveyQuestion,
    SurveyInstance,
    SurveyFrequency,
    SurveyStatus,
    QuestionType,
)


# Sample Organizations
SAMPLE_ORGANIZATIONS = [
    # Internal
    {
        "name": None,  # Set dynamically from tenant name
        "code": "OC",
        "org_type": "internal",
        "size": "enterprise",
        "industry": "Technology",
        "website": None,
        "address": "123 Tech Boulevard, San Francisco, CA 94105",
        "country": "USA",
        "notes": "Internal organization (auto-named from tenant)",
    },
    # Clients
    {
        "name": "Acme Corporation",
        "code": "ACME",
        "org_type": "customer",
        "size": "enterprise",
        "industry": "Manufacturing",
        "website": "https://acme.com",
        "address": "456 Industrial Way, Detroit, MI 48201",
        "country": "USA",
        "notes": "Large manufacturing client with global operations",
    },
    {
        "name": "TechStart Inc",
        "code": "TECH",
        "org_type": "customer",
        "size": "smb",
        "industry": "Technology",
        "website": "https://techstart.io",
        "address": "789 Startup Lane, Austin, TX 78701",
        "country": "USA",
        "notes": "Innovative tech startup",
    },
    # Vendors
    {
        "name": "GlobalSupply International",
        "code": "GSI",
        "org_type": "vendor",
        "size": "mid_market",
        "industry": "Logistics",
        "website": "https://globalsupply.com",
        "address": "321 Logistics Drive, Chicago, IL 60601",
        "country": "USA",
        "notes": "Global logistics and supply chain vendor",
    },
    {
        "name": "CloudServices Pro",
        "code": "CSP",
        "org_type": "vendor",
        "size": "smb",
        "industry": "Cloud Computing",
        "website": "https://cloudservicespro.com",
        "address": "555 Cloud Avenue, Seattle, WA 98101",
        "country": "USA",
        "notes": "Cloud infrastructure and services provider",
    },
    # Partners
    {
        "name": "Strategic Partners LLC",
        "code": "SPL",
        "org_type": "partner",
        "size": "smb",
        "industry": "Consulting",
        "website": "https://strategicpartners.com",
        "address": "777 Partnership Way, New York, NY 10001",
        "country": "USA",
        "notes": "Strategic consulting and implementation partner",
    },
]


# Sample KPIs by category
SAMPLE_KPIS = [
    # Delivery
    {
        "name": "On-Time Delivery Rate",
        "code": "OTD",
        "description": "Percentage of deliverables completed by the agreed deadline",
        "category": "service_delivery",
        "measurement_type": "percentage",
        "target_value": 95.0,
        "weight": 1.0,
    },
    {
        "name": "Quality Score",
        "code": "QS",
        "description": "Overall quality rating of delivered work",
        "category": "quality",
        "measurement_type": "rating",
        "target_value": 4.5,
        "weight": 1.2,
    },
    {
        "name": "Issue Resolution Time",
        "code": "IRT",
        "description": "Average time to resolve reported issues (in hours)",
        "category": "service_delivery",
        "measurement_type": "number",
        "target_value": 24.0,
        "weight": 0.8,
    },
    # Communication
    {
        "name": "Response Time",
        "code": "RT",
        "description": "Average time to respond to communications (in hours)",
        "category": "communication",
        "measurement_type": "number",
        "target_value": 4.0,
        "weight": 0.7,
    },
    {
        "name": "Communication Clarity",
        "code": "CC",
        "description": "Rating of communication clarity and effectiveness",
        "category": "communication",
        "measurement_type": "rating",
        "target_value": 4.0,
        "weight": 0.6,
    },
    # Financial
    {
        "name": "Budget Adherence",
        "code": "BA",
        "description": "Percentage of projects completed within budget",
        "category": "cost_efficiency",
        "measurement_type": "percentage",
        "target_value": 90.0,
        "weight": 1.0,
    },
    {
        "name": "Invoice Accuracy",
        "code": "IA",
        "description": "Percentage of invoices without errors",
        "category": "cost_efficiency",
        "measurement_type": "percentage",
        "target_value": 98.0,
        "weight": 0.5,
    },
    # Compliance
    {
        "name": "SLA Compliance",
        "code": "SLA",
        "description": "Percentage of SLA metrics met",
        "category": "compliance",
        "measurement_type": "percentage",
        "target_value": 95.0,
        "weight": 1.1,
    },
    {
        "name": "Security Compliance",
        "code": "SEC",
        "description": "Security audit score",
        "category": "compliance",
        "measurement_type": "rating",
        "target_value": 4.5,
        "weight": 1.0,
    },
    # Innovation
    {
        "name": "Innovation Score",
        "code": "INV",
        "description": "Rating of proactive improvement suggestions",
        "category": "innovation",
        "measurement_type": "rating",
        "target_value": 3.5,
        "weight": 0.5,
    },
    # Relationship
    {
        "name": "Overall Satisfaction",
        "code": "SAT",
        "description": "Overall relationship satisfaction rating",
        "category": "satisfaction",
        "measurement_type": "rating",
        "target_value": 4.0,
        "weight": 1.0,
    },
    {
        "name": "Collaboration Effectiveness",
        "code": "CE",
        "description": "Rating of collaboration and teamwork",
        "category": "satisfaction",
        "measurement_type": "rating",
        "target_value": 4.0,
        "weight": 0.8,
    },
]


# Sample Survey Template
SAMPLE_SURVEY_TEMPLATE = {
    "name": "Quarterly Relationship Health Survey",
    "description": "Standard quarterly survey for assessing relationship health and perception",
    "frequency": "quarterly",
    "introduction_text": "Thank you for taking the time to complete this survey. Your feedback is valuable in helping us improve our relationship and service delivery.",
    "closing_text": "Thank you for your feedback. Your responses will help us identify areas for improvement.",
    "allow_anonymous": True,
    "require_all_questions": True,
}


# Sample Survey Questions (linked to KPIs by code)
SAMPLE_SURVEY_QUESTIONS = [
    {
        "text": "How would you rate the overall quality of work delivered?",
        "help_text": "Consider accuracy, completeness, and adherence to requirements",
        "question_type": "rating",
        "rating_min_label": "Poor",
        "rating_max_label": "Excellent",
        "kpi_code": "QS",  # Will link to Quality Score KPI
        "sequence": 1,
        "is_required": True,
    },
    {
        "text": "How satisfied are you with the timeliness of deliveries?",
        "help_text": "Consider deadlines and schedule adherence",
        "question_type": "rating",
        "rating_min_label": "Very Unsatisfied",
        "rating_max_label": "Very Satisfied",
        "kpi_code": "OTD",  # Will link to On-Time Delivery Rate
        "sequence": 2,
        "is_required": True,
    },
    {
        "text": "How would you rate the communication effectiveness?",
        "help_text": "Consider clarity, responsiveness, and proactiveness",
        "question_type": "rating",
        "rating_min_label": "Poor",
        "rating_max_label": "Excellent",
        "kpi_code": "CC",  # Will link to Communication Clarity
        "sequence": 3,
        "is_required": True,
    },
    {
        "text": "How well are SLAs and compliance requirements being met?",
        "help_text": "Consider contractual obligations and regulatory compliance",
        "question_type": "rating",
        "rating_min_label": "Poorly",
        "rating_max_label": "Excellently",
        "kpi_code": "SLA",  # Will link to SLA Compliance
        "sequence": 4,
        "is_required": True,
    },
    {
        "text": "How would you rate the overall relationship satisfaction?",
        "help_text": "Overall impression of the working relationship",
        "question_type": "rating",
        "rating_min_label": "Very Unsatisfied",
        "rating_max_label": "Very Satisfied",
        "kpi_code": "SAT",  # Will link to Overall Satisfaction
        "sequence": 5,
        "is_required": True,
    },
    {
        "text": "What areas do you think need the most improvement?",
        "help_text": "Select all that apply",
        "question_type": "multiple_choice",
        "options": ["Communication", "Quality", "Timeliness", "Cost", "Innovation", "None"],
        "kpi_code": None,
        "sequence": 6,
        "is_required": False,
    },
    {
        "text": "Please share any additional comments or suggestions",
        "help_text": "Open feedback",
        "question_type": "text",
        "kpi_code": None,
        "sequence": 7,
        "is_required": False,
    },
]


async def seed_governance_for_tenant(session, admin_user, tenant_id, tenant_name):
    """Seed governance data for a single tenant.

    Returns counts dict for reporting.
    """
    from app.models.tenant import Tenant

    print(f"\n{'='*60}")
    print(f"Seeding governance for: {tenant_name} ({tenant_id})")
    print(f"{'='*60}")

    # Check if tenant already has organizations
    result = await session.execute(
        select(Organization).where(Organization.tenant_id == tenant_id).limit(1)
    )
    if result.scalar_one_or_none():
        print(f"  Tenant {tenant_name} already has organizations — skipping")
        return None

    # Build a short tenant prefix for unique org codes (first 3 chars of tenant name)
    prefix = tenant_name[:3].upper()

    # Create Organizations
    print("\nCreating organizations...")
    orgs = {}
    for org_data in SAMPLE_ORGANIZATIONS:
        data = dict(org_data)
        original_code = data["code"]
        data["code"] = f"{prefix}_{original_code}"  # e.g. "TEC_OC", "LEG_ACME"
        org = Organization(
            id=uuid4(),
            tenant_id=tenant_id,
            **data
        )
        session.add(org)
        orgs[original_code] = org
        print(f"  Created organization: {org.name} ({org.org_type}) [code={data['code']}]")

    await session.flush()

    internal_org = orgs["OC"]

    # Create Business Relationships
    print("\nCreating business relationships...")
    relationships = []
    relationship_configs = [
        {
            "name": "Acme Corporation - Strategic Client",
            "org_a": internal_org,
            "org_b": orgs["ACME"],
            "type": "customer",
            "tier": "strategic",
            "review_days": 30,
        },
        {
            "name": "TechStart - Growth Client",
            "org_a": internal_org,
            "org_b": orgs["TECH"],
            "type": "customer",
            "tier": "operational",
            "review_days": 90,
        },
        {
            "name": "GlobalSupply - Key Vendor",
            "org_a": internal_org,
            "org_b": orgs["GSI"],
            "type": "supplier",
            "tier": "strategic",
            "review_days": 30,
        },
        {
            "name": "CloudServices Pro - Vendor",
            "org_a": internal_org,
            "org_b": orgs["CSP"],
            "type": "supplier",
            "tier": "operational",
            "review_days": 90,
        },
        {
            "name": "Strategic Partners - Implementation Partner",
            "org_a": internal_org,
            "org_b": orgs["SPL"],
            "type": "partner",
            "tier": "strategic",
            "review_days": 30,
        },
    ]

    today = date.today()
    for config in relationship_configs:
        rel = BusinessRelationship(
            id=uuid4(),
            tenant_id=tenant_id,
            org_a_id=config["org_a"].id,
            org_b_id=config["org_b"].id,
            relationship_type=config["type"],
            status="active",
            name=config["name"],
            description=f"Business relationship with {config['org_b'].name}",
            health_score=None,  # Calculated from real data, not fabricated
            last_health_calculation=None,
            governance_tier=config["tier"],
            start_date=today - timedelta(days=365),
            review_frequency_days=config["review_days"],
            next_review_date=today + timedelta(days=config["review_days"]),
        )
        session.add(rel)
        relationships.append(rel)
        print(f"  Created relationship: {rel.name}")

    await session.flush()

    # Add team members to relationships
    print("\nAdding team members to relationships...")
    for rel in relationships:
        team_member = RelationshipTeam(
            id=uuid4(),
            relationship_id=rel.id,
            user_id=admin_user.id,
            role="relationship_manager",
            responsibilities=["Overall relationship management and governance"],
            is_primary=True,
            is_active=True,
            joined_at=datetime.utcnow(),
        )
        session.add(team_member)

    await session.flush()

    # Create KPIs (assigned to the first relationship)
    print("\nCreating KPIs...")
    primary_rel = relationships[0]
    kpis = {}
    for kpi_data in SAMPLE_KPIS:
        kpi = KPI(
            id=uuid4(),
            relationship_id=primary_rel.id,
            **kpi_data,
            is_active=True,
        )
        session.add(kpi)
        kpis[kpi_data["code"]] = kpi
        print(f"  Created KPI: {kpi.name} ({kpi.category})")

    await session.flush()

    # Create Perception Scores using a reproducible random generator
    print("\nCreating sample perception scores...")
    periods = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"]
    rng = random.Random(42)  # Fixed seed for reproducibility

    # Track scores per KPI per period for gap calculation
    # Structure: {kpi_code: {period: {"internal": [scores], "external": [scores]}}}
    scores_by_kpi_period = {}

    for period in periods:
        for kpi_code, kpi in kpis.items():
            if kpi.measurement_type in [KPIMeasurementType.RATING, KPIMeasurementType.PERCENTAGE]:
                # Generate scores in 5.0-9.0 range, no systematic bias
                internal_value = round(rng.uniform(5.0, 9.0), 1)
                external_value = round(rng.uniform(5.0, 9.0), 1)

                # Internal score
                internal_score = PerceptionScore(
                    id=uuid4(),
                    kpi_id=kpi.id,
                    scorer_org_id=internal_org.id,
                    score=internal_value,
                    period=period,
                    is_internal=True,
                    approval_status="approved",
                )
                session.add(internal_score)

                # External score
                external_score = PerceptionScore(
                    id=uuid4(),
                    kpi_id=kpi.id,
                    scorer_org_id=orgs["ACME"].id,
                    score=external_value,
                    period=period,
                    is_internal=False,
                    approval_status="approved",
                )
                session.add(external_score)

                # Track for gap calculation
                if kpi_code not in scores_by_kpi_period:
                    scores_by_kpi_period[kpi_code] = {}
                if period not in scores_by_kpi_period[kpi_code]:
                    scores_by_kpi_period[kpi_code][period] = {"internal": [], "external": []}
                scores_by_kpi_period[kpi_code][period]["internal"].append(internal_value)
                scores_by_kpi_period[kpi_code][period]["external"].append(external_value)

    print(f"  Created perception scores for {len(periods)} periods")

    await session.flush()

    # Create Perception Gaps derived from actual seeded scores
    print("\nCreating perception gaps...")
    latest_period = "2024-Q4"
    for kpi_code, kpi in kpis.items():
        if kpi.measurement_type == KPIMeasurementType.RATING:
            period_data = scores_by_kpi_period.get(kpi_code, {}).get(latest_period)
            if not period_data:
                continue

            # Calculate averages from actual seeded scores
            avg_internal = sum(period_data["internal"]) / len(period_data["internal"])
            avg_external = sum(period_data["external"]) / len(period_data["external"])
            gap_value = round(avg_internal - avg_external, 2)
            severity = PerceptionGap.calculate_severity(gap_value)

            perception_gap = PerceptionGap(
                id=uuid4(),
                kpi_id=kpi.id,
                period=latest_period,
                internal_score=round(avg_internal, 2),
                external_score=round(avg_external, 2),
                gap=gap_value,
                gap_severity=severity,
                requires_action=severity in ("significant", "critical"),
            )
            session.add(perception_gap)

    print(f"  Created perception gaps")

    await session.flush()

    # Create Improvement Points
    print("\nCreating improvement points...")
    improvement_data = [
        {
            "title": "Improve Communication Response Time",
            "description": "External stakeholders perceive slower response times than our internal metrics suggest. Need to investigate and address communication bottlenecks.",
            "priority": "high",
            "status": "in_progress",
            "kpi": kpis["RT"],
        },
        {
            "title": "Enhance Quality Assurance Process",
            "description": "Gap identified between internal quality assessment and client perception. Review QA processes and implement additional checkpoints.",
            "priority": "medium",
            "status": "open",
            "kpi": kpis["QS"],
        },
        {
            "title": "SLA Reporting Enhancement",
            "description": "Improve visibility of SLA compliance metrics to external stakeholders through automated reporting.",
            "priority": "low",
            "status": "open",
            "kpi": kpis["SLA"],
        },
    ]

    improvements = []
    for imp_data in improvement_data:
        improvement = ImprovementPoint(
            id=uuid4(),
            relationship_id=primary_rel.id,
            kpi_id=imp_data["kpi"].id if imp_data["kpi"] else None,
            title=imp_data["title"],
            description=imp_data["description"],
            priority=imp_data["priority"],
            status=imp_data["status"],
            source="perception_gap",
            owner_id=admin_user.id,
            due_date=today + timedelta(days=90),
        )
        session.add(improvement)
        improvements.append(improvement)
        print(f"  Created improvement: {improvement.title}")

    await session.flush()

    # Create Improvement Actions
    print("\nCreating improvement actions...")
    action_data = [
        {
            "improvement": improvements[0],
            "title": "Implement email response SLA monitoring",
            "description": "Set up automated tracking of response times for all client communications",
            "status": "completed",
            "due_days": 14,
        },
        {
            "improvement": improvements[0],
            "title": "Create communication templates",
            "description": "Develop standard response templates to reduce turnaround time",
            "status": "in_progress",
            "due_days": 30,
        },
        {
            "improvement": improvements[0],
            "title": "Weekly communication metrics review",
            "description": "Establish weekly review of communication metrics with team",
            "status": "todo",
            "due_days": 7,
        },
        {
            "improvement": improvements[1],
            "title": "Conduct quality perception survey",
            "description": "Deep dive survey with client to understand quality perception gaps",
            "status": "todo",
            "due_days": 21,
        },
    ]

    for action_info in action_data:
        action = ImprovementAction(
            id=uuid4(),
            improvement_id=action_info["improvement"].id,
            description=f"{action_info['title']}: {action_info['description']}",
            status=action_info["status"],
            owner_id=admin_user.id,
            due_date=today + timedelta(days=action_info["due_days"]),
            completed_at=datetime.now() if action_info["status"] == "completed" else None,
        )
        session.add(action)
        print(f"  Created action: {action_info['title']}")

    await session.flush()

    # Create Survey Template (shared, only create once)
    template = None
    result = await session.execute(
        select(SurveyTemplate).limit(1)
    )
    template = result.scalar_one_or_none()

    if not template:
        print("\nCreating survey template...")
        template = SurveyTemplate(
            id=uuid4(),
            **SAMPLE_SURVEY_TEMPLATE,
        )
        session.add(template)
        await session.flush()
        print(f"  Created template: {template.name}")

        # Create Survey Questions
        print("\nCreating survey questions...")
        for q_data in SAMPLE_SURVEY_QUESTIONS:
            kpi_id = None
            if q_data.get("kpi_code") and q_data["kpi_code"] in kpis:
                kpi_id = kpis[q_data["kpi_code"]].id

            question = SurveyQuestion(
                id=uuid4(),
                template_id=template.id,
                text=q_data["text"],
                help_text=q_data.get("help_text"),
                question_type=q_data["question_type"],
                options=q_data.get("options"),
                rating_min_label=q_data.get("rating_min_label"),
                rating_max_label=q_data.get("rating_max_label"),
                kpi_id=kpi_id,
                sequence=q_data["sequence"],
                is_required=q_data["is_required"],
            )
            session.add(question)
            print(f"  Created question: {q_data['text'][:50]}...")

        await session.flush()

    # Create Survey Instance for this tenant's primary relationship
    print("\nCreating survey instance...")
    instance = SurveyInstance(
        id=uuid4(),
        template_id=template.id,
        relationship_id=primary_rel.id,
        period="2025-Q1",
        status="in_progress",
        scheduled_send_date=today - timedelta(days=7),
        sent_at=datetime.now() - timedelta(days=7),
        due_date=today + timedelta(days=14),
        target_respondent_count=5,
        actual_respondent_count=2,
    )
    session.add(instance)
    print(f"  Created survey instance for: {primary_rel.name}")

    return {
        "organizations": len(SAMPLE_ORGANIZATIONS),
        "relationships": len(relationship_configs),
        "kpis": len(SAMPLE_KPIS),
        "improvements": len(improvement_data),
    }


async def seed_relationship_governance():
    """Seed the database with relationship governance sample data for ALL tenants."""
    print("Starting relationship governance seeding (all tenants)...")

    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)

    # Create session factory
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all admin users (one per tenant)
        result = await session.execute(
            select(User).where(User.role == "admin")
        )
        admin_users = result.scalars().all()

        if not admin_users:
            print("Error: No admin users found. Please run seed_data.py first.")
            return

        # Get tenant names for display
        from app.models.tenant import Tenant
        tenant_map = {}
        for user in admin_users:
            if user.tenant_id and user.tenant_id not in tenant_map:
                t = await session.get(Tenant, user.tenant_id)
                tenant_map[user.tenant_id] = (user, t.name if t else str(user.tenant_id))

        print(f"Found {len(tenant_map)} tenants to seed:")
        for tid, (u, tname) in tenant_map.items():
            print(f"  - {tname} (admin: {u.username})")

        seeded = 0
        skipped = 0
        for tenant_id, (admin_user, tenant_name) in tenant_map.items():
            counts = await seed_governance_for_tenant(session, admin_user, tenant_id, tenant_name)
            if counts:
                seeded += 1
            else:
                skipped += 1

        # Commit all changes
        await session.commit()

    await engine.dispose()

    print("\n" + "=" * 60)
    print("Relationship Governance seeding completed!")
    print("=" * 60)
    print(f"  Tenants seeded: {seeded}")
    print(f"  Tenants skipped (already had data): {skipped}")
    if seeded > 0:
        print(f"  Per tenant: {len(SAMPLE_ORGANIZATIONS)} orgs, 5 relationships, {len(SAMPLE_KPIS)} KPIs")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_relationship_governance())
