"""Auto-provision service for new tenants.

Creates contract-aware demo integration configs, governance data, and mock
activity data when a new tenant is created or when seeding existing tenants.

The provisioner reads the tenant's actual extracted contracts — SLAs,
obligations, renewals, parties, risk scores — and generates contextual mock
integration activity that mirrors what real integrations would look like.

When real integrations are configured later, demo configs (is_demo=True) are
automatically deactivated so they never conflict with production data.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contract import Contract
from app.models.integration import (
    IntegrationConfig,
    IntegrationLog,
    IntegrationSystem,
    IntegrationStatus,
    SLAMeasurement,
)
from app.models.obligation import Obligation
from app.models.sla import ContractSLA
from app.models.snow_sla_mapping import SnowSLAMapping

logger = logging.getLogger(__name__)


# ── Tenant Context ───────────────────────────────────────────────────


@dataclass
class TenantContext:
    """Extracted contract data for a tenant, used to drive realistic mock data."""

    contracts: list = field(default_factory=list)
    slas: list = field(default_factory=list)
    obligations: list = field(default_factory=list)

    # Derived summaries
    counterparties: list = field(default_factory=list)
    high_risk_contracts: list = field(default_factory=list)
    upcoming_renewals: list = field(default_factory=list)
    overdue_obligations: list = field(default_factory=list)
    upcoming_obligations: list = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return len(self.contracts) > 0


async def _build_tenant_context(db: AsyncSession, tenant_id: UUID) -> TenantContext:
    """Read the tenant's actual extracted data to drive mock generation."""
    ctx = TenantContext()
    now = datetime.now(timezone.utc)
    today = now.date()

    # 1. Contracts with key fields
    result = await db.execute(
        select(Contract)
        .where(Contract.tenant_id == tenant_id)
        .where(Contract.status == "completed")
        .order_by(Contract.created_at.desc())
    )
    ctx.contracts = result.scalars().all()

    if not ctx.contracts:
        return ctx

    contract_ids = [c.id for c in ctx.contracts]

    # Derived: counterparties, high-risk, upcoming renewals
    for c in ctx.contracts:
        if c.counterparty and c.counterparty not in ctx.counterparties:
            ctx.counterparties.append(c.counterparty)

        if c.risk_level and c.risk_level.value in ("high", "critical"):
            ctx.high_risk_contracts.append(c)

        if c.expiration_date:
            days_to_expiry = (c.expiration_date - today).days
            if 0 < days_to_expiry <= 90:
                ctx.upcoming_renewals.append(c)

    # 2. SLAs for these contracts
    result = await db.execute(
        select(ContractSLA)
        .where(ContractSLA.contract_id.in_(contract_ids))
        .where(ContractSLA.is_active == True)
    )
    ctx.slas = result.scalars().all()

    # 3. Obligations
    result = await db.execute(
        select(Obligation)
        .where(Obligation.contract_id.in_(contract_ids))
    )
    all_obligations = result.scalars().all()
    ctx.obligations = all_obligations

    for ob in all_obligations:
        if ob.deadline:
            days_to_deadline = (ob.deadline - today).days
            if days_to_deadline < 0 and ob.status != "completed":
                ctx.overdue_obligations.append(ob)
            elif 0 <= days_to_deadline <= 30:
                ctx.upcoming_obligations.append(ob)

    logger.info(
        f"Tenant context: {len(ctx.contracts)} contracts, "
        f"{len(ctx.slas)} SLAs, {len(ctx.obligations)} obligations, "
        f"{len(ctx.counterparties)} counterparties, "
        f"{len(ctx.high_risk_contracts)} high-risk, "
        f"{len(ctx.upcoming_renewals)} renewals due"
    )

    return ctx


# ── Enterprise App Definitions ───────────────────────────────────────

ENTERPRISE_APPS = [
    {
        "system": IntegrationSystem.servicenow,
        "name": "ServiceNow ITSM",
        "description": "IT Service Management - incident tracking, SLA monitoring, and change management",
        "base_url": "https://demo.service-now.com",
        "auth_type": "basic",
        "credentials": {"username": "api_user", "password": "***configured***"},
        "config": {
            "api_version": "v2",
            "assignment_group": "Contract Management",
            "default_category": "Contract",
            "sync_interval_minutes": 60,
        },
        "health_status": IntegrationStatus.healthy,
    },
    {
        "system": IntegrationSystem.salesforce,
        "name": "Salesforce CRM",
        "description": "Customer Relationship Management - account sync, contract tracking, opportunity management",
        "base_url": "https://demo.my.salesforce.com",
        "auth_type": "oauth2",
        "credentials": {
            "client_id": "3MVG9...demo",
            "client_secret": "***configured***",
            "token_url": "https://login.salesforce.com/services/oauth2/token",
        },
        "config": {
            "api_version": "v58.0",
            "sandbox": False,
            "sync_accounts": True,
            "sync_contracts": True,
            "sync_opportunities": True,
        },
        "health_status": IntegrationStatus.healthy,
    },
    {
        "system": IntegrationSystem.teams,
        "name": "Microsoft Teams",
        "description": "Team notifications - contract alerts, SLA breaches, approval workflows",
        "base_url": "https://prod-XX.westus.logic.azure.com/workflows",
        "auth_type": "bearer",
        "credentials": {"webhook_url": "https://prod-XX.westus.logic.azure.com/workflows/***configured***"},
        "config": {
            "channel": "Contract-Alerts",
            "notify_on_upload": True,
            "notify_on_renewal": True,
            "notify_on_sla_breach": True,
            "notify_on_risk": True,
        },
        "health_status": IntegrationStatus.healthy,
    },
    {
        "system": IntegrationSystem.sendgrid,
        "name": "SendGrid Email",
        "description": "Email notifications - renewal reminders, obligation deadlines, report delivery",
        "base_url": "https://api.sendgrid.com",
        "auth_type": "api_key",
        "credentials": {"api_key": "SG.***configured***"},
        "config": {
            "from_email": "notifications@evaluetor.com",
            "from_name": "Evaluetor CLM",
            "template_renewal": "d-abc123",
            "template_obligation": "d-def456",
            "template_report": "d-ghi789",
        },
        "health_status": IntegrationStatus.healthy,
    },
]

# ── Real ServiceNow SLA definitions ─────────────────────────────────

SNOW_SLA_DEFINITIONS = [
    {"sys_id": "2ca94b74c3143200b6dcdfdc64d3ae93", "name": "Priority 1 response (15 minutes)", "collection": "incident", "duration": "15 minutes"},
    {"sys_id": "35420982d732220035ae23c7ce610393", "name": "Priority 1 resolution (1 hour)", "collection": "incident", "duration": "1 hour"},
    {"sys_id": "752bcf74c3143200b6dcdfdc64d3aeeb", "name": "Priority 2 response (1 hour)", "collection": "incident", "duration": "1 hour"},
    {"sys_id": "af420982d732220035ae23c7ce6103f3", "name": "Priority 2 resolution (8 hour)", "collection": "incident", "duration": "8 hours"},
    {"sys_id": "35c213b4c3143200b6dcdfdc64d3ae21", "name": "Priority 3 response (4 hours)", "collection": "incident", "duration": "4 hours"},
    {"sys_id": "375397f4c3143200b6dcdfdc64d3ae60", "name": "Priority 4 response (8 hours)", "collection": "incident", "duration": "8 hours"},
    {"sys_id": "b12a37e0d7322200f2d224837e6103ea", "name": "Priority 4 resolution (2 day)", "collection": "incident", "duration": "2 days"},
    {"sys_id": "58e546f0d7322200f2d224837e610380", "name": "Priority 3 resolution (24 hour)", "collection": "incident", "duration": "24 hours"},
    {"sys_id": "ca93b0e0d7322200f2d224837e6103d0", "name": "Priority 5 response (1 day)", "collection": "incident", "duration": "1 day"},
    {"sys_id": "f0b436a0d7322200f2d224837e6103fb", "name": "Priority 5 resolution (5 day)", "collection": "incident", "duration": "5 days"},
]


# ── Config creation ──────────────────────────────────────────────────

def _traffic_stats(system: IntegrationSystem, num_contracts: int) -> tuple[int, int]:
    """Generate realistic request counts scaled by contract volume."""
    base = max(10, num_contracts * 3)
    scale = {
        IntegrationSystem.servicenow: (8, 25),
        IntegrationSystem.salesforce: (5, 18),
        IntegrationSystem.teams: (2, 9),
        IntegrationSystem.sendgrid: (3, 12),
    }.get(system, (3, 10))

    total = random.randint(base * scale[0], base * scale[1])
    failed = random.randint(max(1, total // 200), max(2, total // 50))
    return total, failed


async def _create_configs(
    db: AsyncSession, tenant_id: UUID, num_contracts: int, now: datetime,
) -> dict[IntegrationSystem, IntegrationConfig]:
    """Create the 4 enterprise integration configs (is_demo=True)."""
    configs = {}

    for app_def in ENTERPRISE_APPS:
        total_req, failed_req = _traffic_stats(app_def["system"], num_contracts)

        config = IntegrationConfig(
            id=uuid4(),
            tenant_id=tenant_id,
            system=app_def["system"],
            name=app_def["name"],
            description=app_def["description"],
            base_url=app_def["base_url"],
            auth_type=app_def["auth_type"],
            credentials=app_def["credentials"],
            config=app_def["config"],
            is_active=True,
            is_default=True,
            is_demo=True,
            health_status=app_def["health_status"],
            last_health_check=now - timedelta(minutes=random.randint(5, 30)),
            last_health_message="Connection successful",
            last_used_at=now - timedelta(minutes=random.randint(1, 60)),
            total_requests=total_req,
            failed_requests=failed_req,
        )
        db.add(config)
        configs[app_def["system"]] = config

    await db.flush()
    return configs


# ── ServiceNow: Contract-aware SLA mappings + measurements ───────────

async def _create_snow_data(
    db: AsyncSession,
    tenant_id: UUID,
    snow_config: IntegrationConfig,
    ctx: TenantContext,
    now: datetime,
) -> dict:
    """Create SNOW SLA mappings and measurements from actual contract SLAs."""
    counts = {"mappings": 0, "measurements": 0, "logs": 0}

    # Map SNOW definitions to actual platform SLAs by metric type
    response_slas = [s for s in ctx.slas if s.metric_type and s.metric_type.value in ("response_time", "uptime_percentage", "availability")]
    resolution_slas = [s for s in ctx.slas if s.metric_type and s.metric_type.value in ("resolution_time", "recovery_time")]
    other_slas = [s for s in ctx.slas if s not in response_slas and s not in resolution_slas]
    all_slas = response_slas + resolution_slas + other_slas

    for i, sla_def in enumerate(SNOW_SLA_DEFINITIONS):
        is_response = "response" in sla_def["name"].lower()
        # Smart matching: response SLAs map to response-type metrics, etc.
        platform_sla = None
        if is_response and response_slas:
            platform_sla = response_slas[i % len(response_slas)]
        elif not is_response and resolution_slas:
            platform_sla = resolution_slas[i % len(resolution_slas)]
        elif all_slas:
            platform_sla = all_slas[i % len(all_slas)]

        mapping_status = "mapped" if platform_sla else "pending"

        mapping = SnowSLAMapping(
            id=uuid4(),
            integration_config_id=snow_config.id,
            tenant_id=tenant_id,
            snow_sys_id=sla_def["sys_id"],
            snow_sla_name=sla_def["name"],
            snow_metric_type="response_time" if is_response else "resolution_time",
            snow_target=sla_def["duration"],
            platform_sla_id=platform_sla.id if platform_sla else None,
            mapping_status=mapping_status,
            last_synced_at=now - timedelta(hours=random.randint(1, 24)),
            sync_metadata={
                "collection": sla_def["collection"],
                "source": "auto_sync",
                "synced_by": "system",
            },
        )
        db.add(mapping)
        counts["mappings"] += 1

        # Create SLA measurements with values realistic to the actual target
        if platform_sla:
            target_val = float(platform_sla.target_value or 99.0)

            for days_ago in range(30):
                if random.random() > 0.6:
                    continue

                # ~15% breach rate — more breaches for critical SLAs
                severity_weight = {"critical": 0.20, "high": 0.18, "medium": 0.12, "low": 0.08}
                sev_key = platform_sla.severity.value if platform_sla.severity else "medium"
                breach_prob = severity_weight.get(sev_key, 0.15)

                if random.random() < breach_prob:
                    actual = target_val * random.uniform(0.70, 0.95)
                    is_breach = True
                else:
                    actual = target_val * random.uniform(0.98, 1.05)
                    is_breach = False

                measurement = SLAMeasurement(
                    id=uuid4(),
                    sla_id=platform_sla.id,
                    source="servicenow",
                    source_reference=str(snow_config.id),
                    measurement_date=now - timedelta(days=days_ago, hours=random.randint(0, 23)),
                    period_start=now - timedelta(days=days_ago + 1),
                    period_end=now - timedelta(days=days_ago),
                    actual_value=round(actual, 2),
                    target_value=round(target_val, 2),
                    is_breach=is_breach,
                    deviation_percent=round(((actual - target_val) / target_val) * 100, 2),
                )
                db.add(measurement)
                counts["measurements"] += 1

    # SNOW integration logs — reference actual contract data
    snow_ops = []

    # Incidents for overdue obligations
    for ob in ctx.overdue_obligations[:5]:
        contract = next((c for c in ctx.contracts if c.id == ob.contract_id), None)
        party = contract.counterparty if contract else "Unknown"
        snow_ops.append({
            "method": "POST", "endpoint": "/api/now/table/incident",
            "operation": "create_incident", "is_success": True,
            "payload": {
                "short_description": f"Overdue obligation: {ob.description[:80]}",
                "counterparty": party,
                "priority": "2" if ob.is_critical else "3",
                "category": "Contract Compliance",
            },
            "external_id": f"INC{random.randint(100000, 999999)}",
        })

    # SLA sync calls for each mapped SLA
    for sla in ctx.slas[:8]:
        contract = next((c for c in ctx.contracts if c.id == sla.contract_id), None)
        snow_ops.append({
            "method": "GET", "endpoint": "/api/now/table/task_sla",
            "operation": "get_sla_performance", "is_success": True,
            "payload": {
                "sla_name": sla.sla_name,
                "contract": contract.filename[:60] if contract else "N/A",
                "metric": sla.metric_type.value if sla.metric_type else "custom",
            },
            "external_id": None,
        })

    # Generic SNOW operations to fill out log volume
    generic_ops = [
        ("GET", "/api/now/table/incident", "get_incidents", True),
        ("PATCH", "/api/now/table/incident/{sys_id}", "update_incident", True),
        ("GET", "/api/now/table/contract_sla", "get_sla_definitions", True),
        ("POST", "/api/now/table/incident", "create_incident", False),
    ]
    for _ in range(random.randint(10, 25)):
        m, ep, op, ok = random.choice(generic_ops)
        snow_ops.append({
            "method": m, "endpoint": ep, "operation": op, "is_success": ok,
            "payload": {"tenant": str(snow_config.tenant_id)},
            "external_id": f"INC{random.randint(100000, 999999)}" if ok and "incident" in ep else None,
        })

    for op_data in snow_ops:
        counts["logs"] += 1
        log_time = now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        duration = random.randint(80, 800) if op_data["is_success"] else random.randint(5000, 30000)
        log = IntegrationLog(
            id=uuid4(),
            integration_id=snow_config.id,
            operation=op_data["operation"],
            method=op_data["method"],
            endpoint=op_data["endpoint"],
            status_code=200 if op_data["is_success"] else random.choice([408, 500, 502, 503]),
            request_payload=op_data["payload"],
            response_payload={"status": "ok"} if op_data["is_success"] else {"error": "timeout"},
            external_id=op_data.get("external_id"),
            started_at=log_time,
            completed_at=log_time + timedelta(milliseconds=duration),
            duration_ms=duration,
            is_success=op_data["is_success"],
            error_message=None if op_data["is_success"] else "Request timeout",
            retry_count=0 if op_data["is_success"] else random.randint(1, 3),
        )
        db.add(log)

    return counts


# ── Salesforce: Contract-aware account/opportunity logs ──────────────

async def _create_sfdc_data(
    db: AsyncSession,
    sfdc_config: IntegrationConfig,
    ctx: TenantContext,
    now: datetime,
) -> int:
    """Create Salesforce logs referencing actual counterparties and contract values."""
    log_count = 0

    sfdc_ops = []

    # Account sync for each counterparty
    for party in ctx.counterparties[:10]:
        acct_id = f"001{random.randint(1000000, 9999999)}"
        sfdc_ops.append({
            "method": "GET",
            "endpoint": f"/services/data/v58.0/sobjects/Account/{acct_id}",
            "operation": "get_account",
            "is_success": True,
            "payload": {"account_name": party, "synced_fields": ["Name", "BillingAddress", "Industry"]},
            "external_id": acct_id,
        })
        sfdc_ops.append({
            "method": "PATCH",
            "endpoint": f"/services/data/v58.0/sobjects/Account/{acct_id}",
            "operation": "update_account",
            "is_success": True,
            "payload": {"account_name": party, "updated_fields": ["Contract_Status__c", "Last_Contract_Date__c"]},
            "external_id": acct_id,
        })

    # Renewal review tasks for contracts expiring soon
    for c in ctx.upcoming_renewals[:5]:
        task_id = f"00T{random.randint(1000000, 9999999)}"
        sfdc_ops.append({
            "method": "POST",
            "endpoint": "/services/data/v58.0/sobjects/Task",
            "operation": "create_review_task",
            "is_success": True,
            "payload": {
                "subject": f"Review renewal: {c.filename[:50]}",
                "counterparty": c.counterparty,
                "expiration": c.expiration_date.isoformat() if c.expiration_date else None,
                "value": str(c.contract_value) if c.contract_value else None,
            },
            "external_id": task_id,
        })

    # Contract value sync
    for c in ctx.contracts[:8]:
        if c.contract_value:
            sfdc_ops.append({
                "method": "GET",
                "endpoint": "/services/data/v58.0/query",
                "operation": "query_contracts",
                "is_success": True,
                "payload": {
                    "query": f"SELECT Id, ContractNumber FROM Contract WHERE Account.Name = '{(c.counterparty or 'N/A')[:40]}'",
                    "records_returned": random.randint(1, 5),
                },
                "external_id": None,
            })

    # Generic filler
    for _ in range(random.randint(5, 15)):
        sfdc_ops.append({
            "method": "POST",
            "endpoint": "/services/data/v58.0/sobjects/Task",
            "operation": "create_task",
            "is_success": random.random() > 0.05,
            "payload": {"type": "contract_sync"},
            "external_id": f"00T{random.randint(1000000, 9999999)}",
        })

    for op_data in sfdc_ops:
        log_count += 1
        log_time = now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        duration = random.randint(100, 600) if op_data["is_success"] else random.randint(5000, 15000)
        log = IntegrationLog(
            id=uuid4(),
            integration_id=sfdc_config.id,
            operation=op_data["operation"],
            method=op_data["method"],
            endpoint=op_data["endpoint"],
            status_code=200 if op_data["is_success"] else random.choice([400, 401, 500]),
            request_payload=op_data["payload"],
            response_payload={"status": "ok"} if op_data["is_success"] else {"error": "authentication_failure"},
            external_id=op_data.get("external_id"),
            started_at=log_time,
            completed_at=log_time + timedelta(milliseconds=duration),
            duration_ms=duration,
            is_success=op_data["is_success"],
            error_message=None if op_data["is_success"] else "SFDC API Error",
            retry_count=0 if op_data["is_success"] else 1,
        )
        db.add(log)

    return log_count


# ── Teams: Contract-aware notifications ──────────────────────────────

async def _create_teams_data(
    db: AsyncSession,
    teams_config: IntegrationConfig,
    ctx: TenantContext,
    now: datetime,
) -> int:
    """Create Teams notification logs for actual risk/renewal/SLA events."""
    log_count = 0
    teams_ops = []

    # Risk alerts for high-risk contracts
    for c in ctx.high_risk_contracts[:5]:
        teams_ops.append({
            "operation": "notify_contract_risk",
            "is_success": True,
            "payload": {
                "channel": "Contract-Alerts",
                "title": f"High Risk Contract Alert",
                "contract": c.filename[:60],
                "counterparty": c.counterparty,
                "risk_level": c.risk_level.value if c.risk_level else "high",
                "risk_score": c.risk_score,
            },
        })

    # Renewal notifications
    for c in ctx.upcoming_renewals[:5]:
        days_left = (c.expiration_date - now.date()).days if c.expiration_date else 0
        teams_ops.append({
            "operation": "notify_contract_renewal",
            "is_success": True,
            "payload": {
                "channel": "Contract-Alerts",
                "title": f"Renewal Due in {days_left} Days",
                "contract": c.filename[:60],
                "counterparty": c.counterparty,
                "expiration": c.expiration_date.isoformat() if c.expiration_date else None,
                "auto_renewal": c.auto_renewal,
            },
        })

    # SLA breach notifications
    breach_slas = [s for s in ctx.slas if s.consecutive_breaches and s.consecutive_breaches > 0]
    for sla in breach_slas[:3]:
        contract = next((c for c in ctx.contracts if c.id == sla.contract_id), None)
        teams_ops.append({
            "operation": "notify_sla_breach",
            "is_success": True,
            "payload": {
                "channel": "Contract-Alerts",
                "title": f"SLA Breach: {sla.sla_name}",
                "contract": contract.filename[:60] if contract else "N/A",
                "target": str(sla.target_value),
                "consecutive_breaches": sla.consecutive_breaches,
            },
        })

    # Generic notifications to fill volume
    for _ in range(random.randint(8, 20)):
        teams_ops.append({
            "operation": "send_notification",
            "is_success": random.random() > 0.02,
            "payload": {"channel": "Contract-Alerts", "type": "system_update"},
        })

    for op_data in teams_ops:
        log_count += 1
        log_time = now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        duration = random.randint(200, 1500) if op_data["is_success"] else random.randint(5000, 30000)
        log = IntegrationLog(
            id=uuid4(),
            integration_id=teams_config.id,
            operation=op_data["operation"],
            method="POST",
            endpoint="/workflows/trigger",
            status_code=200 if op_data["is_success"] else 502,
            request_payload=op_data["payload"],
            response_payload={"status": "ok"} if op_data["is_success"] else {"error": "webhook_timeout"},
            started_at=log_time,
            completed_at=log_time + timedelta(milliseconds=duration),
            duration_ms=duration,
            is_success=op_data["is_success"],
            error_message=None if op_data["is_success"] else "Webhook timeout",
            retry_count=0 if op_data["is_success"] else random.randint(1, 2),
        )
        db.add(log)

    return log_count


# ── SendGrid: Contract-aware emails ─────────────────────────────────

async def _create_email_data(
    db: AsyncSession,
    email_config: IntegrationConfig,
    ctx: TenantContext,
    now: datetime,
) -> int:
    """Create SendGrid email logs for actual obligation and renewal reminders."""
    log_count = 0
    email_ops = []

    # Renewal reminder emails
    for c in ctx.upcoming_renewals[:5]:
        days_left = (c.expiration_date - now.date()).days if c.expiration_date else 0
        email_ops.append({
            "operation": "send_renewal_reminder",
            "is_success": True,
            "payload": {
                "to": "contract-team@company.com",
                "template": "d-abc123",
                "subject": f"Contract Renewal: {c.filename[:40]} expires in {days_left} days",
                "counterparty": c.counterparty,
                "value": str(c.contract_value) if c.contract_value else None,
            },
        })

    # Obligation deadline alerts
    for ob in ctx.upcoming_obligations[:8]:
        contract = next((c for c in ctx.contracts if c.id == ob.contract_id), None)
        email_ops.append({
            "operation": "send_obligation_alert",
            "is_success": True,
            "payload": {
                "to": "legal-team@company.com",
                "template": "d-def456",
                "subject": f"Upcoming Deadline: {ob.description[:50]}",
                "deadline": ob.deadline.isoformat() if ob.deadline else None,
                "contract": contract.filename[:40] if contract else "N/A",
                "priority": ob.priority,
            },
        })

    # Overdue obligation escalations
    for ob in ctx.overdue_obligations[:3]:
        contract = next((c for c in ctx.contracts if c.id == ob.contract_id), None)
        email_ops.append({
            "operation": "send_obligation_alert",
            "is_success": True,
            "payload": {
                "to": "legal-team@company.com",
                "template": "d-def456",
                "subject": f"OVERDUE: {ob.description[:50]}",
                "deadline": ob.deadline.isoformat() if ob.deadline else None,
                "contract": contract.filename[:40] if contract else "N/A",
                "escalation": True,
            },
        })

    # Weekly report emails
    for weeks_ago in range(4):
        email_ops.append({
            "operation": "send_report",
            "is_success": True,
            "payload": {
                "to": "management@company.com",
                "template": "d-ghi789",
                "subject": "Weekly Contract Intelligence Report",
                "contracts_active": len(ctx.contracts),
                "slas_tracked": len(ctx.slas),
                "obligations_pending": len([o for o in ctx.obligations if o.status != "completed"]),
            },
        })

    # Generic filler
    for _ in range(random.randint(5, 12)):
        email_ops.append({
            "operation": random.choice(["send_renewal_reminder", "send_obligation_alert", "send_report"]),
            "is_success": random.random() > 0.03,
            "payload": {"type": "system_notification"},
        })

    for op_data in email_ops:
        log_count += 1
        log_time = now - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        duration = random.randint(300, 2000) if op_data["is_success"] else random.randint(5000, 10000)
        log = IntegrationLog(
            id=uuid4(),
            integration_id=email_config.id,
            operation=op_data["operation"],
            method="POST",
            endpoint="/v3/mail/send",
            status_code=202 if op_data["is_success"] else random.choice([400, 429, 500]),
            request_payload=op_data["payload"],
            response_payload={"status": "accepted"} if op_data["is_success"] else {"error": "rate_limit_exceeded"},
            started_at=log_time,
            completed_at=log_time + timedelta(milliseconds=duration),
            duration_ms=duration,
            is_success=op_data["is_success"],
            error_message=None if op_data["is_success"] else "SendGrid rate limit",
            retry_count=0 if op_data["is_success"] else 1,
        )
        db.add(log)

    return log_count


# ── Main provisioning function ───────────────────────────────────────

async def provision_integrations(
    db: AsyncSession,
    tenant_id: UUID,
    tenant_name: str,
) -> dict:
    """Provision contract-aware demo integration data for a tenant.

    Reads the tenant's actual extracted contracts, SLAs, obligations, and
    renewals, then generates contextual mock integration activity that
    mirrors what real integrations would look like.

    All created configs are marked is_demo=True. When a real integration is
    configured for the same system, the demo config should be deactivated
    via deactivate_demo_config().

    Idempotent — skips if tenant already has integration configs.

    Returns:
        Dict with counts of created items.
    """
    # Check if tenant already has integrations
    result = await db.execute(
        select(IntegrationConfig).where(IntegrationConfig.tenant_id == tenant_id).limit(1)
    )
    if result.scalar_one_or_none():
        logger.info(f"Tenant {tenant_name} already has integrations — skipping")
        return {"skipped": True}

    now = datetime.now(timezone.utc)

    # 1. Build context from actual extracted contract data
    ctx = await _build_tenant_context(db, tenant_id)

    # 2. Create integration configs (is_demo=True)
    configs = await _create_configs(db, tenant_id, len(ctx.contracts), now)

    counts = {"configs": len(configs), "mappings": 0, "measurements": 0, "logs": 0}

    # 3. ServiceNow — SLA mappings + measurements + contextual logs
    snow_config = configs.get(IntegrationSystem.servicenow)
    if snow_config:
        snow_counts = await _create_snow_data(db, tenant_id, snow_config, ctx, now)
        counts["mappings"] += snow_counts["mappings"]
        counts["measurements"] += snow_counts["measurements"]
        counts["logs"] += snow_counts["logs"]

    await db.flush()

    # 4. Salesforce — account syncs + renewal tasks using real counterparties
    sfdc_config = configs.get(IntegrationSystem.salesforce)
    if sfdc_config:
        counts["logs"] += await _create_sfdc_data(db, sfdc_config, ctx, now)

    # 5. Teams — alerts for real risks, renewals, SLA breaches
    teams_config = configs.get(IntegrationSystem.teams)
    if teams_config:
        counts["logs"] += await _create_teams_data(db, teams_config, ctx, now)

    # 6. SendGrid — emails for real obligation deadlines, renewals
    email_config = configs.get(IntegrationSystem.sendgrid)
    if email_config:
        counts["logs"] += await _create_email_data(db, email_config, ctx, now)

    await db.flush()

    logger.info(
        f"Provisioned integrations for {tenant_name}: "
        f"{counts['configs']} configs, {counts['mappings']} mappings, "
        f"{counts['measurements']} measurements, {counts['logs']} logs "
        f"(from {len(ctx.contracts)} contracts, {len(ctx.slas)} SLAs, "
        f"{len(ctx.obligations)} obligations)"
    )

    return counts


# ── Lifecycle management ─────────────────────────────────────────────

async def deactivate_demo_config(
    db: AsyncSession,
    tenant_id: UUID,
    system: IntegrationSystem,
) -> IntegrationConfig | None:
    """Deactivate demo config for a system when a real one is being configured.

    Call this when a user configures a real integration for a system that
    already has a demo config. The demo config is deactivated (not deleted)
    so historical demo data is preserved but no longer active.

    Returns:
        The deactivated demo config, or None if no demo config existed.
    """
    result = await db.execute(
        select(IntegrationConfig)
        .where(IntegrationConfig.tenant_id == tenant_id)
        .where(IntegrationConfig.system == system)
        .where(IntegrationConfig.is_demo == True)
        .where(IntegrationConfig.is_active == True)
    )
    demo_config = result.scalar_one_or_none()

    if demo_config:
        demo_config.is_active = False
        demo_config.is_default = False
        await db.flush()
        logger.info(f"Deactivated demo {system.value} config for tenant {tenant_id}")

    return demo_config
