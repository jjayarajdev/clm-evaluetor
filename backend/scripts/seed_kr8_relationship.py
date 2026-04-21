"""Seed realistic governance data for the KR8 AI Inc. relationship.

Populates: perception scores, perception gaps, team members,
improvement points, relationship status history.

Usage:
    cd backend && uv run python -m scripts.seed_kr8_relationship
"""

import asyncio
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker, engine


# === Constants ===

TENANT_ID = uuid.UUID("120d3426-2f15-4f96-b46b-d27a8866e34a")  # Acme Corp
RELATIONSHIP_ID = uuid.UUID("68d9ce17-93cd-4a40-a3ae-a1bf087a5c4e")
ORG_KR8_ID = uuid.UUID("cbfcfbca-4af5-46bc-adbb-a009987fdd7c")
ORG_INTERNAL_ID = uuid.UUID("3bffdb9a-7da5-4886-8fd8-17082465d514")

# Users
ADMIN_ID = uuid.UUID("1187b9bc-9cee-474e-bba5-7d9d288e2306")
LEGAL_ID = uuid.UUID("6f4354fd-e68b-4f01-be24-8c3ecd8cc7ad")


async def seed():
    async with async_session_maker() as db:
        # Get KPI IDs
        result = await db.execute(
            text("SELECT id, name FROM kpis WHERE relationship_id = :rid ORDER BY name"),
            {"rid": str(RELATIONSHIP_ID)},
        )
        kpis = {row[1]: row[0] for row in result.all()}
        print(f"Found {len(kpis)} KPIs: {list(kpis.keys())}")

        if not kpis:
            print("ERROR: No KPIs found. Upload the addendum first.")
            return

        # =========================================================
        # 1. PERCEPTION SCORES — internal and external per KPI
        # =========================================================
        print("\n--- Seeding Perception Scores ---")

        # Realistic scores: internal team rates themselves higher than customer rates them
        score_data = {
            "Platform Availability": [
                # (period, internal_score, external_score)
                ("2024-Q1", 9.2, 8.5),
                ("2024-Q2", 9.0, 7.8),
                ("2024-Q3", 9.5, 8.8),
                ("2024-Q4", 9.3, 8.2),
                ("2025-Q1", 9.1, 8.0),
                ("2025-Q2", 9.4, 8.6),
            ],
            "Response Time - Standard Queries": [
                ("2024-Q1", 8.5, 7.0),
                ("2024-Q2", 8.0, 6.5),
                ("2024-Q3", 8.8, 7.5),
                ("2024-Q4", 8.2, 6.8),
                ("2025-Q1", 7.8, 6.0),
                ("2025-Q2", 8.5, 7.2),
            ],
            "Incident Response - Critical": [
                ("2024-Q1", 8.0, 7.5),
                ("2024-Q2", 7.5, 5.5),  # gap event — missed SLA in Q2
                ("2024-Q3", 8.5, 7.0),
                ("2024-Q4", 8.8, 8.0),
                ("2025-Q1", 9.0, 8.2),
                ("2025-Q2", 8.5, 7.8),
            ],
            "Incident Resolution - Critical": [
                ("2024-Q1", 7.5, 6.5),
                ("2024-Q2", 7.0, 5.0),  # significant gap
                ("2024-Q3", 8.0, 7.0),
                ("2024-Q4", 8.5, 7.5),
                ("2025-Q1", 8.0, 7.2),
                ("2025-Q2", 8.2, 7.5),
            ],
            "Data Processing Accuracy - Structured Data": [
                ("2024-Q1", 9.0, 8.5),
                ("2024-Q2", 9.2, 8.8),
                ("2024-Q3", 9.5, 9.0),
                ("2024-Q4", 9.3, 8.7),
                ("2025-Q1", 9.0, 8.5),
                ("2025-Q2", 9.4, 9.0),
            ],
            "Data Processing Accuracy - Unstructured Data": [
                ("2024-Q1", 8.0, 6.5),
                ("2024-Q2", 8.2, 7.0),
                ("2024-Q3", 8.5, 7.5),
                ("2024-Q4", 8.0, 6.8),
                ("2025-Q1", 7.8, 6.0),  # customer unhappy
                ("2025-Q2", 8.5, 7.0),
            ],
        }

        for kpi_name, periods in score_data.items():
            kpi_id = kpis.get(kpi_name)
            if not kpi_id:
                print(f"  SKIP: KPI '{kpi_name}' not found")
                continue

            for period, internal, external in periods:
                # Internal score
                await db.execute(
                    text("""
                        INSERT INTO perception_scores (id, kpi_id, scorer_org_id, scored_by_user_id, score, period, comments, is_internal, scored_at, created_at, approval_status)
                        VALUES (:id, :kpi_id, :org_id, :user_id, :score, :period, :comments, true, :scored_at, :created_at, 'approved')
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "kpi_id": str(kpi_id),
                        "org_id": str(ORG_INTERNAL_ID),
                        "user_id": str(ADMIN_ID),
                        "score": internal,
                        "period": period,
                        "comments": f"Internal assessment for {period}",
                        "scored_at": datetime(int(period[:4]), int(period[-1]) * 3, 15),
                        "created_at": datetime.utcnow(),
                    },
                )
                # External score
                await db.execute(
                    text("""
                        INSERT INTO perception_scores (id, kpi_id, scorer_org_id, scored_by_user_id, score, period, comments, is_internal, scored_at, created_at, approval_status)
                        VALUES (:id, :kpi_id, :org_id, :user_id, :score, :period, :comments, false, :scored_at, :created_at, 'approved')
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "kpi_id": str(kpi_id),
                        "org_id": str(ORG_KR8_ID),
                        "user_id": str(ADMIN_ID),
                        "score": external,
                        "period": period,
                        "comments": f"KR8 AI customer feedback for {period}",
                        "scored_at": datetime(int(period[:4]), int(period[-1]) * 3, 20),
                        "created_at": datetime.utcnow(),
                    },
                )
            print(f"  Scores: {kpi_name} — 6 periods x 2 perspectives")

        # =========================================================
        # 2. PERCEPTION GAPS — computed from scores
        # =========================================================
        print("\n--- Seeding Perception Gaps ---")

        def gap_severity(gap_val: float) -> str:
            abs_gap = abs(gap_val)
            if abs_gap >= 2.5:
                return "critical"
            elif abs_gap >= 1.5:
                return "significant"
            elif abs_gap >= 0.8:
                return "moderate"
            elif abs_gap >= 0.3:
                return "minor"
            return "minor"  # aligned not in enum, use minor

        gap_ids = {}  # (kpi_name, period) -> gap_id for linking improvements
        for kpi_name, periods in score_data.items():
            kpi_id = kpis.get(kpi_name)
            if not kpi_id:
                continue
            for period, internal, external in periods:
                gap_val = internal - external
                severity = gap_severity(gap_val)
                gid = uuid.uuid4()
                gap_ids[(kpi_name, period)] = gid
                await db.execute(
                    text("""
                        INSERT INTO perception_gaps (id, kpi_id, period, internal_score, external_score, gap, gap_severity, requires_action, notes, calculated_at, created_at, updated_at)
                        VALUES (:id, :kpi_id, :period, :int_score, :ext_score, :gap, :severity, :action, :notes, :calc_at, :created_at, :updated_at)
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "id": str(gid),
                        "kpi_id": str(kpi_id),
                        "period": period,
                        "int_score": internal,
                        "ext_score": external,
                        "gap": round(gap_val, 2),
                        "severity": severity,
                        "action": gap_val >= 1.5,
                        "notes": f"{'Action required: ' if gap_val >= 1.5 else ''}Internal={internal}, External={external}" ,
                        "calc_at": datetime.utcnow(),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    },
                )
            print(f"  Gaps: {kpi_name} — 6 periods")

        print("  Gaps complete (latest scores derived from gap-summary API)")

        # =========================================================
        # 3. TEAM MEMBERS
        # =========================================================
        print("\n--- Seeding Team Members ---")

        team_members = [
            (ADMIN_ID, "relationship_manager", True, ["Quarterly business reviews", "Escalation point", "Contract renewals"]),
            (LEGAL_ID, "operations_lead", False, ["SLA monitoring", "Compliance tracking", "Obligation management"]),
        ]

        for user_id, role, is_primary, responsibilities in team_members:
            await db.execute(
                text("""
                    INSERT INTO relationship_teams (id, relationship_id, user_id, role, responsibilities, is_primary, is_active, joined_at, created_at, updated_at)
                    VALUES (:id, :rel_id, :user_id, :role, :resp, :primary, true, :joined, :created, :updated)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "rel_id": str(RELATIONSHIP_ID),
                    "user_id": str(user_id),
                    "role": role,
                    "resp": str(responsibilities).replace("'", '"'),  # JSON array
                    "primary": is_primary,
                    "joined": datetime(2024, 1, 15),
                    "created": datetime.utcnow(),
                    "updated": datetime.utcnow(),
                },
            )
            print(f"  Added: {role} (user_id={user_id})")

        # =========================================================
        # 4. IMPROVEMENT POINTS
        # =========================================================
        print("\n--- Seeding Improvement Points ---")

        improvements = [
            {
                "title": "Improve Incident Resolution SLA Compliance",
                "description": "Customer perception of critical incident resolution times is significantly lower than our internal assessment. Gap was 2.0 in Q2 2024. Implement dedicated escalation queue and automated alerting for P1 incidents.",
                "source": "perception_gap",
                "priority": "high",
                "status": "in_progress",
                "gap_key": ("Incident Resolution - Critical", "2024-Q2"),
                "target_outcome": "Reduce perception gap to < 0.5 by Q3 2025",
                "due_date": date(2025, 9, 30),
                "impact_score": 85,
            },
            {
                "title": "Enhance Unstructured Data Processing Accuracy",
                "description": "Persistent gap between internal and external perception of unstructured data classification quality. Customer scored 6.0 in Q1 2025 vs. internal 7.8. Root cause: Edge cases in financial document parsing not covered by training data.",
                "source": "perception_gap",
                "priority": "high",
                "status": "in_progress",
                "gap_key": ("Data Processing Accuracy - Unstructured Data", "2025-Q1"),
                "target_outcome": "Achieve external score ≥ 8.0 for unstructured data accuracy",
                "due_date": date(2025, 8, 31),
                "impact_score": 75,
            },
            {
                "title": "Reduce API Response Time Variability",
                "description": "Response time KPI shows consistent 1.3-point gap. Customer experiences periodic slowdowns during peak hours (10am-2pm ET). Investigate query optimization and caching strategy.",
                "source": "perception_gap",
                "priority": "medium",
                "status": "open",
                "gap_key": ("Response Time - Standard Queries", "2025-Q2"),
                "target_outcome": "P95 response time under 150ms consistently; perception gap < 0.5",
                "due_date": date(2025, 12, 31),
                "impact_score": 60,
            },
            {
                "title": "Establish Proactive Communication Cadence",
                "description": "Feedback from Q2 2024 QBR: customer feels reactive, not proactive. Implement monthly status reports and bi-weekly check-in calls. Share platform roadmap quarterly.",
                "source": "customer_feedback",
                "priority": "medium",
                "status": "completed",
                "gap_key": None,
                "target_outcome": "Customer satisfaction with communication ≥ 8.5",
                "due_date": date(2024, 12, 31),
                "impact_score": 70,
            },
            {
                "title": "Conduct Annual Security Audit Review",
                "description": "Per Addendum No. 1 Section 3.5, annual penetration testing results must be shared. Schedule joint review session with KR8 AI security team. Document findings and remediation timeline.",
                "source": "internal_audit",
                "priority": "medium",
                "status": "open",
                "gap_key": None,
                "target_outcome": "Complete security review with zero critical findings unresolved",
                "due_date": date(2025, 6, 30),
                "impact_score": 80,
            },
            {
                "title": "Contract Risk: IP Ownership Clarity",
                "description": "Medium-risk intellectual property clause detected in the MSA. Three IP clauses found — need to clarify ownership of AI model derivatives and training data rights during next renewal cycle.",
                "source": "contract_risk",
                "priority": "high",
                "status": "open",
                "gap_key": None,
                "target_outcome": "Renegotiate IP terms to clearly delineate model derivative ownership",
                "due_date": date(2025, 12, 31),
                "impact_score": 90,
            },
        ]

        improvement_ids = {}  # title -> id
        for imp in improvements:
            gap_id = None
            kpi_id = None
            if imp["gap_key"]:
                gap_id = gap_ids.get(imp["gap_key"])
                kpi_id = kpis.get(imp["gap_key"][0])

            imp_id = uuid.uuid4()
            improvement_ids[imp["title"]] = imp_id
            await db.execute(
                text("""
                    INSERT INTO improvement_points (id, relationship_id, kpi_id, gap_id, title, description, source, priority, status, owner_id, due_date, target_outcome, impact_score, created_at, updated_at)
                    VALUES (:id, :rel_id, :kpi_id, :gap_id, :title, :desc, :source, :priority, :status, :owner, :due, :target, :impact, :created, :updated)
                """),
                {
                    "id": str(imp_id),
                    "rel_id": str(RELATIONSHIP_ID),
                    "kpi_id": str(kpi_id) if kpi_id else None,
                    "gap_id": str(gap_id) if gap_id else None,
                    "title": imp["title"],
                    "desc": imp["description"],
                    "source": imp["source"],
                    "priority": imp["priority"],
                    "status": imp["status"],
                    "owner": str(ADMIN_ID),
                    "due": imp["due_date"],
                    "target": imp["target_outcome"],
                    "impact": imp["impact_score"],
                    "created": datetime.utcnow(),
                    "updated": datetime.utcnow(),
                },
            )
            print(f"  Added: [{imp['priority']}] {imp['title'][:50]}...")

        # =========================================================
        # 4b. IMPROVEMENT ACTIONS — concrete tasks for each improvement
        # =========================================================
        print("\n--- Seeding Improvement Actions ---")

        actions_data = {
            "Improve Incident Resolution SLA Compliance": [
                ("Set up dedicated P1 escalation queue in PagerDuty", "completed", ADMIN_ID, date(2024, 8, 15)),
                ("Hire 2 additional SREs for on-call rotation", "completed", ADMIN_ID, date(2024, 10, 1)),
                ("Implement automated P1 alerting with 5-min SLA countdown", "in_progress", LEGAL_ID, date(2025, 6, 30)),
                ("Conduct monthly incident response drills", "todo", ADMIN_ID, date(2025, 9, 30)),
            ],
            "Enhance Unstructured Data Processing Accuracy": [
                ("Audit failed classifications from Q4 2024 — Q1 2025", "completed", LEGAL_ID, date(2025, 3, 31)),
                ("Expand training dataset with 500 financial document samples", "in_progress", ADMIN_ID, date(2025, 6, 30)),
                ("Deploy retrained model to staging and run regression tests", "todo", ADMIN_ID, date(2025, 7, 31)),
                ("Customer UAT sign-off on improved accuracy", "todo", LEGAL_ID, date(2025, 8, 31)),
            ],
            "Reduce API Response Time Variability": [
                ("Profile peak-hour query patterns and identify bottlenecks", "completed", ADMIN_ID, date(2025, 4, 30)),
                ("Implement query result caching for repeated analytics calls", "todo", ADMIN_ID, date(2025, 8, 31)),
                ("Add CDN for static asset delivery", "todo", LEGAL_ID, date(2025, 10, 31)),
            ],
            "Establish Proactive Communication Cadence": [
                ("Set up monthly automated status report generation", "completed", ADMIN_ID, date(2024, 8, 31)),
                ("Schedule bi-weekly 30-min check-in calls", "completed", ADMIN_ID, date(2024, 9, 15)),
                ("Share Q4 2024 platform roadmap with customer", "completed", LEGAL_ID, date(2024, 12, 15)),
            ],
            "Conduct Annual Security Audit Review": [
                ("Schedule penetration test with third-party auditor", "todo", ADMIN_ID, date(2025, 5, 15)),
                ("Compile SOC 2 Type II evidence package", "todo", LEGAL_ID, date(2025, 6, 15)),
            ],
            "Contract Risk: IP Ownership Clarity": [
                ("Legal review of AI model derivative ownership clauses", "in_progress", LEGAL_ID, date(2025, 8, 31)),
                ("Draft amendment for training data rights clarification", "todo", LEGAL_ID, date(2025, 10, 31)),
                ("Negotiate revised IP terms with KR8 AI legal team", "todo", ADMIN_ID, date(2025, 12, 31)),
            ],
        }

        for imp_title, actions in actions_data.items():
            imp_id = improvement_ids.get(imp_title)
            if not imp_id:
                continue
            for seq, (desc, status, assignee, due) in enumerate(actions, 1):
                completed_at = datetime(due.year, due.month, min(due.day, 28)) if status == "completed" else None
                started_at = datetime(due.year, due.month, 1) if status in ("completed", "in_progress") else None
                await db.execute(
                    text("""
                        INSERT INTO improvement_actions (id, improvement_id, description, status, sequence, owner_id, due_date, started_at, completed_at, created_at, updated_at)
                        VALUES (:id, :imp_id, :desc, :status, :seq, :owner, :due, :started, :completed, :created, :updated)
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "imp_id": str(imp_id),
                        "desc": desc,
                        "status": status,
                        "seq": seq,
                        "owner": str(assignee),
                        "due": due,
                        "started": started_at,
                        "completed": completed_at,
                        "created": datetime.utcnow(),
                        "updated": datetime.utcnow(),
                    },
                )
            print(f"  Actions for '{imp_title[:40]}': {len(actions)} tasks")

        # =========================================================
        # 5. RELATIONSHIP STATUS HISTORY
        # =========================================================
        print("\n--- Seeding Relationship Status History ---")

        history = [
            ("2024-Q1", "good", None, 78, "quarterly_review", "Initial onboarding period. Platform deployed successfully. Minor integration issues resolved."),
            ("2024-Q2", "concerning", "good", 65, "sla_breach", "Critical incident resolution SLA missed twice. Customer escalated to VP level. Root cause: understaffed on-call rotation."),
            ("2024-Q3", "acceptable", "concerning", 72, "quarterly_review", "Recovery from Q2 issues. Hired 2 additional SREs. Response times improved. Customer cautiously optimistic."),
            ("2024-Q4", "good", "acceptable", 80, "quarterly_review", "Strong quarter. All SLAs met. New data processing features well received. Customer renewed for 2025."),
            ("2025-Q1", "acceptable", "good", 74, "quarterly_review", "Slight dip due to unstructured data accuracy concerns. Customer flagged issues with financial document parsing."),
            ("2025-Q2", "good", "acceptable", 82, "quarterly_review", "Improvements from Q1 action items visible. Customer engagement strong. 6 KPIs now tracked via Addendum SLAs."),
        ]

        prev_status = None
        for period, status, previous, score, trigger, notes in history:
            year = int(period[:4])
            quarter = int(period[-1])
            await db.execute(
                text("""
                    INSERT INTO relationship_status_history (id, tenant_id, relationship_id, status, previous_status, overall_score, period, recorded_date, recorded_by, notes, trigger, created_at)
                    VALUES (:id, :tenant_id, :rel_id, :status, :prev, :score, :period, :recorded, :recorded_by, :notes, :trigger, :created)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "tenant_id": str(TENANT_ID),
                    "rel_id": str(RELATIONSHIP_ID),
                    "status": status,
                    "prev": previous,
                    "score": score,
                    "period": period,
                    "recorded": datetime(year, quarter * 3, 28),
                    "recorded_by": str(ADMIN_ID),
                    "notes": notes,
                    "trigger": trigger,
                    "created": datetime.utcnow(),
                },
            )
            print(f"  {period}: {status} (score: {score})")

        # =========================================================
        # 6. UPDATE RELATIONSHIP METADATA
        # =========================================================
        print("\n--- Updating Relationship Metadata ---")
        await db.execute(
            text("""
                UPDATE business_relationships SET
                    description = :desc,
                    governance_tier = 'strategic',
                    review_frequency_days = 90,
                    next_review_date = :next_review,
                    health_score = 82,
                    last_health_calculation = :now
                WHERE id = :rel_id
            """),
            {
                "rel_id": str(RELATIONSHIP_ID),
                "desc": "Strategic AI platform partnership. KR8 AI provides core ML/AI software for FOXO's data analytics pipeline. $2.5M MSA with $15K/mo SLA management addendum. 6 KPIs tracked, quarterly business reviews.",
                "next_review": datetime(2025, 9, 30),
                "now": datetime.utcnow(),
            },
        )

        # Also give users display names
        await db.execute(
            text("UPDATE users SET full_name = 'Alex Morgan' WHERE id = :id AND (full_name IS NULL OR full_name = '')"),
            {"id": str(ADMIN_ID)},
        )
        await db.execute(
            text("UPDATE users SET full_name = 'Jordan Chen' WHERE id = :id AND (full_name IS NULL OR full_name = '')"),
            {"id": str(LEGAL_ID)},
        )

        await db.commit()
        print("\n=== Seed complete! ===")
        print("Refresh the relationship page to see the data.")


if __name__ == "__main__":
    asyncio.run(seed())
