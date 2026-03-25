#!/usr/bin/env python3
"""
Seed script to populate ServiceNow integration data.
Creates integration configs, SLA mappings, measurements, and logs
using real SLA definitions from algoleaptest.service-now.com.

Run with: python -m scripts.seed_servicenow
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4, UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.integration import (
    IntegrationConfig,
    IntegrationLog,
    IntegrationSystem,
    IntegrationStatus,
    SLAMeasurement,
)
from app.models.snow_sla_mapping import SnowSLAMapping

# ── Tenant IDs ────────────────────────────────────────────────────────
ACME_TENANT = UUID("10000000-0000-0000-0000-000000000001")
TECHSTART_TENANT = UUID("10000000-0000-0000-0000-000000000002")

# ── Real ServiceNow SLA definitions from algoleaptest.service-now.com ──
SNOW_SLA_DEFINITIONS = [
    {
        "sys_id": "2ca94b74c3143200b6dcdfdc64d3ae93",
        "name": "Priority 1 response (15 minutes)",
        "collection": "incident",
        "duration": "15 minutes",
    },
    {
        "sys_id": "35420982d732220035ae23c7ce610393",
        "name": "Priority 1 resolution (1 hour)",
        "collection": "incident",
        "duration": "1 hour",
    },
    {
        "sys_id": "752bcf74c3143200b6dcdfdc64d3aeeb",
        "name": "Priority 2 response (1 hour)",
        "collection": "incident",
        "duration": "1 hour",
    },
    {
        "sys_id": "af420982d732220035ae23c7ce6103f3",
        "name": "Priority 2 resolution (8 hour)",
        "collection": "incident",
        "duration": "8 hours",
    },
    {
        "sys_id": "35c213b4c3143200b6dcdfdc64d3ae21",
        "name": "Priority 3 response (4 hours)",
        "collection": "incident",
        "duration": "4 hours",
    },
    {
        "sys_id": "375397f4c3143200b6dcdfdc64d3ae60",
        "name": "Priority 4 response (8 hours)",
        "collection": "incident",
        "duration": "8 hours",
    },
    {
        "sys_id": "b12a37e0d7322200f2d224837e6103ea",
        "name": "Priority 4 resolution (2 day)",
        "collection": "incident",
        "duration": "2 days",
    },
    {
        "sys_id": "b0e39bf4c3143200b6dcdfdc64d3ae19",
        "name": "Priority 5 response (40 hours)",
        "collection": "incident",
        "duration": "40 hours",
    },
    {
        "sys_id": "3b524982d732220035ae23c7ce6103e4",
        "name": "SAN 001 contract resolution (3.5 hour)",
        "collection": "incident",
        "duration": "3.5 hours",
    },
    {
        "sys_id": "b222c582d732220035ae23c7ce6103a7",
        "name": "Database group resolution (P1 only)",
        "collection": "incident",
        "duration": "1 hour",
    },
]

# ── SLA name matching rules ──────────────────────────────────────────
# Maps SNOW SLA names to patterns we'll search for in platform ContractSLA names.
# Each entry: (snow_sys_id, list of platform SLA name substrings to match)
ACME_MAPPING_RULES = [
    # CareerSource MSA + InfraManagement SOW
    ("2ca94b74c3143200b6dcdfdc64d3ae93", ["Priority 1 Incident Response", "P1 Incident Response", "P1 Response Time"]),
    ("35420982d732220035ae23c7ce610393", ["Priority 1 Incident Resolution", "P1 Resolution Time", "P1 Incident Resolution"]),
    ("752bcf74c3143200b6dcdfdc64d3aeeb", ["Priority 2 Incident Response", "P2 Incident Response"]),
    ("af420982d732220035ae23c7ce6103f3", ["Priority 2 Incident Resolution", "P2 Resolution"]),
    ("35c213b4c3143200b6dcdfdc64d3ae21", ["Priority 3 Incident Response", "P3 Response"]),
    ("375397f4c3143200b6dcdfdc64d3ae60", ["Helpdesk Answer Time"]),
    # These won't match — pending/ignored
    ("b12a37e0d7322200f2d224837e6103ea", []),  # P4 resolution - no match
    ("3b524982d732220035ae23c7ce6103e4", []),  # SAN 001 - no match
]

TECHSTART_MAPPING_RULES = [
    # MSA_TechServices_Acme
    ("2ca94b74c3143200b6dcdfdc64d3ae93", ["Response Time - Priority 1"]),
    ("35420982d732220035ae23c7ce610393", ["Resolution Time - Priority 1"]),
    ("752bcf74c3143200b6dcdfdc64d3aeeb", ["Response Time - Priority 2"]),
    ("af420982d732220035ae23c7ce6103f3", ["Resolution Time - Priority 2"]),
    ("35c213b4c3143200b6dcdfdc64d3ae21", ["Response Time - Priority 3"]),
    ("375397f4c3143200b6dcdfdc64d3ae60", ["Response Time - Priority 4"]),
    ("b12a37e0d7322200f2d224837e6103ea", ["Resolution Time - Priority 4"]),
    ("b0e39bf4c3143200b6dcdfdc64d3ae19", []),  # P5 response - no match
    ("b222c582d732220035ae23c7ce6103a7", []),  # Database group - no match
    ("3b524982d732220035ae23c7ce6103e4", []),  # SAN 001 - no match
]


def generate_measurement_value(target_value: float, metric_type: str, month_idx: int) -> float:
    """Generate realistic SLA measurement values with seasonal variation.

    Creates data where most months meet target, but some have near-misses
    or breaches — realistic for enterprise IT operations.
    """
    # Response/resolution times: actual should be LOWER than target (faster is better)
    # Uptime/availability: actual should be HIGHER than target (more uptime is better)
    is_time_metric = metric_type in ("response_time", "resolution_time", "delivery_time", "recovery_time")

    if is_time_metric:
        # For time metrics, lower actual = better performance
        # Target is max allowed time; actual should usually be under
        base_performance = random.uniform(0.55, 0.85)  # Usually 55-85% of target
        seasonal = [0.0, 0.02, -0.01, 0.05, 0.03, -0.02]  # Q4 and March busy
        variation = seasonal[month_idx % 6] + random.uniform(-0.05, 0.05)
        ratio = base_performance + variation

        # 15% chance of a near-miss (90-100% of target)
        if random.random() < 0.15:
            ratio = random.uniform(0.90, 1.00)
        # 8% chance of a breach (exceeds target)
        if random.random() < 0.08:
            ratio = random.uniform(1.05, 1.35)

        return round(target_value * max(0.3, ratio), 2)
    else:
        # For percentage metrics (uptime, quality), higher = better
        # Actual should usually meet or exceed target
        gap = 100.0 - target_value  # headroom above target
        base_above = random.uniform(0.3, 0.8) * gap  # Usually 30-80% of headroom
        seasonal = [0.01, -0.02, 0.0, -0.03, 0.02, -0.01]
        variation = seasonal[month_idx % 6] * gap + random.uniform(-0.02, 0.02) * gap

        actual = target_value + base_above + variation

        # 12% chance of dip below target
        if random.random() < 0.12:
            actual = target_value - random.uniform(0.1, 2.0)
        # 5% chance of serious breach
        if random.random() < 0.05:
            actual = target_value - random.uniform(2.0, 5.0)

        return round(min(100.0, max(0.0, actual)), 2)


async def find_platform_sla(db: AsyncSession, tenant_id: UUID, name_patterns: list[str]) -> dict | None:
    """Find a platform ContractSLA matching any of the given name patterns."""
    for pattern in name_patterns:
        result = await db.execute(
            text("""
                SELECT cs.id, cs.sla_name, cs.metric_type, cs.target_value, cs.metric_unit
                FROM contract_slas cs
                JOIN contracts c ON cs.contract_id = c.id
                WHERE c.tenant_id = :tenant_id
                  AND cs.sla_name ILIKE :pattern
                LIMIT 1
            """),
            {"tenant_id": str(tenant_id), "pattern": f"%{pattern}%"},
        )
        row = result.first()
        if row:
            return {
                "id": row.id,
                "sla_name": row.sla_name,
                "metric_type": row.metric_type,
                "target_value": float(row.target_value) if row.target_value else None,
                "metric_unit": row.metric_unit,
            }
    return None


async def seed_servicenow():
    """Main seed function."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # ── Clean existing SNOW seed data ─────────────────────────────
        print("Cleaning existing ServiceNow seed data...")
        await db.execute(delete(SLAMeasurement).where(SLAMeasurement.source == "servicenow"))
        await db.execute(delete(SnowSLAMapping))
        # Delete tenant-scoped SNOW integration configs (leave the old tenant_id=NULL ones)
        await db.execute(
            delete(IntegrationConfig).where(
                IntegrationConfig.system == IntegrationSystem.servicenow,
                IntegrationConfig.tenant_id.isnot(None),
            )
        )
        await db.commit()
        print("  Cleaned.")

        # ── Create Integration Configs ────────────────────────────────
        print("\nCreating ServiceNow integration configs...")

        acme_config = IntegrationConfig(
            id=uuid4(),
            tenant_id=ACME_TENANT,
            system=IntegrationSystem.servicenow,
            name="Acme Corp ServiceNow",
            description="Production ServiceNow instance for Acme Corp IT service management",
            base_url="https://algoleaptest.service-now.com",
            auth_type="basic",
            credentials={
                "username": "jay.jay",
                "password": "Algoleap@321",
            },
            config={
                "api_version": "v2",
                "assignment_group": "Acme IT Operations",
                "sync_interval_hours": 6,
            },
            is_active=True,
            is_default=True,
            health_status=IntegrationStatus.healthy,
            last_health_check=datetime.now(timezone.utc) - timedelta(hours=2),
            last_health_message="Connection successful - 12 SLA definitions found",
            total_requests=342,
            failed_requests=3,
            last_used_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db.add(acme_config)

        techstart_config = IntegrationConfig(
            id=uuid4(),
            tenant_id=TECHSTART_TENANT,
            system=IntegrationSystem.servicenow,
            name="TechStart SNOW Instance",
            description="ServiceNow instance for TechStart managed services SLA tracking",
            base_url="https://algoleaptest.service-now.com",
            auth_type="basic",
            credentials={
                "username": "jay.jay",
                "password": "Algoleap@321",
            },
            config={
                "api_version": "v2",
                "assignment_group": "TechStart Engineering",
                "sync_interval_hours": 12,
            },
            is_active=True,
            is_default=True,
            health_status=IntegrationStatus.healthy,
            last_health_check=datetime.now(timezone.utc) - timedelta(hours=6),
            last_health_message="Connection successful - 12 SLA definitions found",
            total_requests=87,
            failed_requests=1,
            last_used_at=datetime.now(timezone.utc) - timedelta(hours=6),
        )
        db.add(techstart_config)
        await db.flush()
        print(f"  Acme config:     {acme_config.id}")
        print(f"  TechStart config: {techstart_config.id}")

        # ── Create SLA Mappings ───────────────────────────────────────
        print("\nCreating SLA mappings...")
        snow_defs_by_id = {d["sys_id"]: d for d in SNOW_SLA_DEFINITIONS}
        all_mapped_slas = []  # Track (sla_id, target_value, metric_type) for measurements

        # Acme mappings
        acme_mapped = 0
        acme_pending = 0
        acme_ignored = 0
        for snow_sys_id, patterns in ACME_MAPPING_RULES:
            snow_def = snow_defs_by_id.get(snow_sys_id)
            if not snow_def:
                continue

            platform_sla = None
            status = "pending"
            if patterns:
                platform_sla = await find_platform_sla(db, ACME_TENANT, patterns)
                if platform_sla:
                    status = "mapped"
                    acme_mapped += 1
                else:
                    acme_pending += 1
            else:
                # No patterns = intentionally pending or ignored
                if snow_sys_id == "3b524982d732220035ae23c7ce6103e4":
                    status = "ignored"
                    acme_ignored += 1
                else:
                    acme_pending += 1

            mapping = SnowSLAMapping(
                id=uuid4(),
                tenant_id=ACME_TENANT,
                integration_config_id=acme_config.id,
                snow_sys_id=snow_sys_id,
                snow_sla_name=snow_def["name"],
                snow_metric_type=snow_def["collection"],
                snow_target=snow_def["duration"],
                platform_sla_id=platform_sla["id"] if platform_sla else None,
                mapping_status=status,
                last_synced_at=datetime.now(timezone.utc) - timedelta(hours=2),
                sync_metadata=snow_def,
            )
            db.add(mapping)

            if platform_sla and status == "mapped":
                all_mapped_slas.append({
                    "sla_id": platform_sla["id"],
                    "target_value": platform_sla["target_value"],
                    "metric_type": platform_sla["metric_type"],
                    "snow_sys_id": snow_sys_id,
                })

        print(f"  Acme:     {acme_mapped} mapped, {acme_pending} pending, {acme_ignored} ignored")

        # TechStart mappings
        ts_mapped = 0
        ts_pending = 0
        ts_ignored = 0
        for snow_sys_id, patterns in TECHSTART_MAPPING_RULES:
            snow_def = snow_defs_by_id.get(snow_sys_id)
            if not snow_def:
                continue

            platform_sla = None
            status = "pending"
            if patterns:
                platform_sla = await find_platform_sla(db, TECHSTART_TENANT, patterns)
                if platform_sla:
                    status = "mapped"
                    ts_mapped += 1
                else:
                    ts_pending += 1
            else:
                if snow_sys_id in ("b222c582d732220035ae23c7ce6103a7", "3b524982d732220035ae23c7ce6103e4"):
                    status = "ignored"
                    ts_ignored += 1
                else:
                    ts_pending += 1

            mapping = SnowSLAMapping(
                id=uuid4(),
                tenant_id=TECHSTART_TENANT,
                integration_config_id=techstart_config.id,
                snow_sys_id=snow_sys_id,
                snow_sla_name=snow_def["name"],
                snow_metric_type=snow_def["collection"],
                snow_target=snow_def["duration"],
                platform_sla_id=platform_sla["id"] if platform_sla else None,
                mapping_status=status,
                last_synced_at=datetime.now(timezone.utc) - timedelta(hours=6),
                sync_metadata=snow_def,
            )
            db.add(mapping)

            if platform_sla and status == "mapped":
                all_mapped_slas.append({
                    "sla_id": platform_sla["id"],
                    "target_value": platform_sla["target_value"],
                    "metric_type": platform_sla["metric_type"],
                    "snow_sys_id": snow_sys_id,
                })

        print(f"  TechStart: {ts_mapped} mapped, {ts_pending} pending, {ts_ignored} ignored")
        await db.flush()

        # ── Create SLA Measurements (6 months of data) ────────────────
        print(f"\nCreating SLA measurements for {len(all_mapped_slas)} mapped SLAs...")
        measurement_count = 0
        now = datetime.now(timezone.utc)

        for sla_info in all_mapped_slas:
            target = sla_info["target_value"]
            if target is None:
                continue

            metric_type = sla_info["metric_type"]
            is_time_metric = metric_type in ("response_time", "resolution_time", "delivery_time", "recovery_time")

            for month_idx in range(6):
                # Monthly periods: Oct 2025 → Mar 2026
                period_start = datetime(2025, 10 + month_idx if month_idx < 3 else month_idx - 2,
                                        1, tzinfo=timezone.utc)
                if month_idx < 3:
                    period_start = period_start.replace(year=2025, month=10 + month_idx)
                else:
                    period_start = period_start.replace(year=2026, month=month_idx - 2)

                # End of month
                if period_start.month == 12:
                    period_end = period_start.replace(year=period_start.year + 1, month=1) - timedelta(seconds=1)
                else:
                    period_end = period_start.replace(month=period_start.month + 1) - timedelta(seconds=1)

                actual = generate_measurement_value(target, metric_type, month_idx)

                # Determine breach
                if is_time_metric:
                    is_breach = actual > target  # Took longer than allowed
                    deviation = ((actual - target) / target * 100) if target > 0 else 0
                else:
                    is_breach = actual < target  # Below required threshold
                    deviation = ((target - actual) / target * 100) if target > 0 else 0

                measurement = SLAMeasurement(
                    id=uuid4(),
                    sla_id=sla_info["sla_id"],
                    measurement_date=period_end,
                    period_start=period_start,
                    period_end=period_end,
                    actual_value=actual,
                    target_value=target,
                    is_breach=is_breach,
                    deviation_percent=round(deviation, 2) if is_breach else 0.0,
                    source="servicenow",
                    source_reference=f"SNOW:{sla_info['snow_sys_id']}",
                    event_generated=is_breach,
                )
                db.add(measurement)
                measurement_count += 1

        print(f"  Created {measurement_count} measurement records (6 months x {len(all_mapped_slas)} SLAs)")
        await db.flush()

        # ── Create Integration Logs ───────────────────────────────────
        print("\nCreating integration logs...")
        log_entries = []

        # Acme logs — shows a history of syncs and health checks
        acme_log_data = [
            # Initial setup and first sync
            {
                "operation": "health_check", "method": "GET",
                "endpoint": "/api/now/table/sys_properties?sysparm_limit=1",
                "status_code": 200, "is_success": True, "duration_ms": 423,
                "started_at": now - timedelta(days=30),
            },
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 200, "is_success": True, "duration_ms": 1847,
                "started_at": now - timedelta(days=30, hours=-1),
            },
            # Weekly syncs
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 200, "is_success": True, "duration_ms": 1623,
                "started_at": now - timedelta(days=23),
            },
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 504, "is_success": False, "duration_ms": 30000,
                "error_message": "Gateway Timeout - ServiceNow instance maintenance window",
                "started_at": now - timedelta(days=16),
            },
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 200, "is_success": True, "duration_ms": 1756,
                "started_at": now - timedelta(days=16, hours=-2),
            },
            {
                "operation": "health_check", "method": "GET",
                "endpoint": "/api/now/table/sys_properties?sysparm_limit=1",
                "status_code": 200, "is_success": True, "duration_ms": 389,
                "started_at": now - timedelta(days=9),
            },
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 200, "is_success": True, "duration_ms": 1534,
                "started_at": now - timedelta(days=2),
            },
            {
                "operation": "health_check", "method": "GET",
                "endpoint": "/api/now/table/sys_properties?sysparm_limit=1",
                "status_code": 200, "is_success": True, "duration_ms": 412,
                "started_at": now - timedelta(hours=2),
            },
        ]

        for log_data in acme_log_data:
            started = log_data["started_at"]
            log = IntegrationLog(
                id=uuid4(),
                integration_id=acme_config.id,
                operation=log_data["operation"],
                method=log_data["method"],
                endpoint=log_data["endpoint"],
                status_code=log_data["status_code"],
                is_success=log_data["is_success"],
                error_message=log_data.get("error_message"),
                duration_ms=log_data["duration_ms"],
                started_at=started,
                completed_at=started + timedelta(milliseconds=log_data["duration_ms"]),
            )
            db.add(log)
            log_entries.append(log)

        # TechStart logs
        ts_log_data = [
            {
                "operation": "health_check", "method": "GET",
                "endpoint": "/api/now/table/sys_properties?sysparm_limit=1",
                "status_code": 200, "is_success": True, "duration_ms": 567,
                "started_at": now - timedelta(days=14),
            },
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 200, "is_success": True, "duration_ms": 2134,
                "started_at": now - timedelta(days=14, hours=-1),
            },
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 200, "is_success": True, "duration_ms": 1876,
                "started_at": now - timedelta(days=7),
            },
            {
                "operation": "health_check", "method": "GET",
                "endpoint": "/api/now/table/sys_properties?sysparm_limit=1",
                "status_code": 200, "is_success": True, "duration_ms": 445,
                "started_at": now - timedelta(hours=6),
            },
            {
                "operation": "sync_sla_definitions", "method": "GET",
                "endpoint": "/api/now/table/contract_sla?sysparm_limit=100",
                "status_code": 200, "is_success": True, "duration_ms": 1943,
                "started_at": now - timedelta(hours=6, minutes=-5),
            },
        ]

        for log_data in ts_log_data:
            started = log_data["started_at"]
            log = IntegrationLog(
                id=uuid4(),
                integration_id=techstart_config.id,
                operation=log_data["operation"],
                method=log_data["method"],
                endpoint=log_data["endpoint"],
                status_code=log_data["status_code"],
                is_success=log_data["is_success"],
                error_message=log_data.get("error_message"),
                duration_ms=log_data["duration_ms"],
                started_at=started,
                completed_at=started + timedelta(milliseconds=log_data["duration_ms"]),
            )
            db.add(log)
            log_entries.append(log)

        print(f"  Created {len(log_entries)} integration log entries")

        # ── Commit everything ─────────────────────────────────────────
        await db.commit()
        print("\n✓ ServiceNow seed data complete!")
        print(f"  Integration configs: 2 (Acme + TechStart)")
        print(f"  SLA mappings: {acme_mapped + acme_pending + acme_ignored + ts_mapped + ts_pending + ts_ignored}")
        print(f"  SLA measurements: {measurement_count}")
        print(f"  Integration logs: {len(log_entries)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_servicenow())
