"""Seed mock enterprise systems with realistic data tied to CLM entities.

CLM Entities this maps to:
- Acme Corp (tenant) with admin/legal users
- KR8 AI Inc. (organization, customer)
- FOXO Technologies (counterparty from MSA)
- Our Company (internal org)
- Business Relationship: Acme Corp <-> KR8 AI
"""

import random
from datetime import datetime, timedelta

from app.db import engine, SessionLocal, Base
from app.models import (
    SFAccount, SFContact, SFOpportunity, SFUser,
    WDWorker, WDOrganization, WDPosition,
    SAPPurchaseOrder, SAPPOLineItem, SAPInvoice, SAPPayment,
    SNOWSLAResult, SNOWIncident, SNOWChangeRequest,
    QSurvey, QResponse,
    DDService, DDSLO, DDMonitorStatus, DDIncident,
    gen_id,
)


def seed_all():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        _seed_salesforce(db)
        _seed_workday(db)
        _seed_sap(db)
        _seed_servicenow(db)
        _seed_qualtrics(db)
        _seed_datadog(db)
        db.commit()
        print("Seeded all 6 enterprise systems successfully.")
    finally:
        db.close()


# =============================================================================
# Salesforce
# =============================================================================

def _seed_salesforce(db):
    # Users (account owners)
    users = [
        SFUser(id="sf-u1", name="Sarah Mitchell", email="sarah.mitchell@acmecorp.com", role="VP Sales", department="Sales"),
        SFUser(id="sf-u2", name="James Rodriguez", email="james.rodriguez@acmecorp.com", role="Account Executive", department="Sales"),
        SFUser(id="sf-u3", name="Emily Chen", email="emily.chen@acmecorp.com", role="Customer Success Manager", department="CS"),
    ]
    db.add_all(users)

    # Accounts (matching CLM organizations)
    accounts = [
        SFAccount(
            id="sf-kr8", name="KR8 AI Inc.", account_number="ACC-10042",
            account_type="Customer", industry="Technology", annual_revenue=12_000_000,
            number_of_employees=85, billing_city="Las Vegas", billing_state="NV",
            billing_country="US", website="https://kr8ai.com", phone="+1-702-555-0180",
            owner_id="sf-u2",
        ),
        SFAccount(
            id="sf-foxo", name="FOXO Technologies Inc.", account_number="ACC-10043",
            account_type="Customer", industry="InsurTech", annual_revenue=28_000_000,
            number_of_employees=150, billing_city="Minneapolis", billing_state="MN",
            billing_country="US", website="https://foxo.com", phone="+1-612-555-0199",
            owner_id="sf-u2",
        ),
        SFAccount(
            id="sf-stream", name="Streamline Health Solutions", account_number="ACC-10044",
            account_type="Customer", industry="Healthcare IT", annual_revenue=95_000_000,
            number_of_employees=450, billing_city="Atlanta", billing_state="GA",
            billing_country="US", website="https://streamlinehealth.net",
            owner_id="sf-u1",
        ),
        SFAccount(
            id="sf-globex", name="Globex Corporation", account_number="ACC-10045",
            account_type="Partner", industry="Conglomerate", annual_revenue=500_000_000,
            number_of_employees=5000, billing_city="London", billing_country="UK",
            owner_id="sf-u1",
        ),
        SFAccount(
            id="sf-initech", name="Initech Solutions", account_number="ACC-10046",
            account_type="Vendor", industry="IT Services", annual_revenue=8_000_000,
            number_of_employees=60, billing_city="Austin", billing_state="TX",
            billing_country="US", owner_id="sf-u3",
        ),
    ]
    db.add_all(accounts)

    # Contacts
    contacts = [
        SFContact(account_id="sf-kr8", first_name="David", last_name="Park", email="david.park@kr8ai.com",
                   title="CTO", department="Engineering", is_primary=True),
        SFContact(account_id="sf-kr8", first_name="Lisa", last_name="Wang", email="lisa.wang@kr8ai.com",
                   title="VP Engineering", department="Engineering"),
        SFContact(account_id="sf-kr8", first_name="Mike", last_name="Torres", email="mike.torres@kr8ai.com",
                   title="Head of Legal", department="Legal"),
        SFContact(account_id="sf-foxo", first_name="Andrew", last_name="Poole", email="apoole@foxo.com",
                   title="CEO", department="Executive", is_primary=True),
        SFContact(account_id="sf-foxo", first_name="Jennifer", last_name="Lee", email="jlee@foxo.com",
                   title="General Counsel", department="Legal"),
        SFContact(account_id="sf-stream", first_name="Robert", last_name="Kim", email="rkim@streamlinehealth.net",
                   title="VP Procurement", department="Procurement", is_primary=True),
        SFContact(account_id="sf-globex", first_name="Margaret", last_name="Blackwell", email="m.blackwell@globex.com",
                   title="Chief Partnerships Officer", department="Partnerships", is_primary=True),
        SFContact(account_id="sf-initech", first_name="Bill", last_name="Lumbergh", email="bill@initech.com",
                   title="VP Operations", department="Operations", is_primary=True),
    ]
    db.add_all(contacts)

    # Opportunities
    now = datetime.utcnow()
    opps = [
        SFOpportunity(
            account_id="sf-kr8", name="KR8 AI - MSA Renewal 2026",
            stage="Negotiation", amount=2_500_000, close_date=now + timedelta(days=60),
            probability=75, contract_type="Renewal", owner_id="sf-u2",
            description="Annual MSA renewal with expanded SLA terms",
        ),
        SFOpportunity(
            account_id="sf-kr8", name="KR8 AI - Professional Services SOW",
            stage="Proposal", amount=180_000, close_date=now + timedelta(days=30),
            probability=60, contract_type="New", owner_id="sf-u2",
            description="Custom ML model training engagement",
        ),
        SFOpportunity(
            account_id="sf-foxo", name="FOXO - Platform License Renewal",
            stage="Closed Won", amount=1_800_000, close_date=now - timedelta(days=15),
            probability=100, contract_type="Renewal", owner_id="sf-u2",
        ),
        SFOpportunity(
            account_id="sf-stream", name="Streamline Health - Enterprise CLM",
            stage="Qualification", amount=500_000, close_date=now + timedelta(days=90),
            probability=30, contract_type="New", owner_id="sf-u1",
        ),
        SFOpportunity(
            account_id="sf-globex", name="Globex - APAC Expansion Amendment",
            stage="Proposal", amount=750_000, close_date=now + timedelta(days=45),
            probability=50, contract_type="Amendment", owner_id="sf-u1",
        ),
    ]
    db.add_all(opps)
    print("  Salesforce: 3 users, 5 accounts, 8 contacts, 5 opportunities")


# =============================================================================
# Workday
# =============================================================================

def _seed_workday(db):
    # Org structure
    orgs = [
        WDOrganization(id="wd-org-exec", name="Executive Office", org_code="EXEC", org_type="Division"),
        WDOrganization(id="wd-org-legal", name="Legal Department", org_code="LEGAL", org_type="Department", parent_id="wd-org-exec"),
        WDOrganization(id="wd-org-sales", name="Sales", org_code="SALES", org_type="Department", parent_id="wd-org-exec"),
        WDOrganization(id="wd-org-cs", name="Customer Success", org_code="CS", org_type="Department", parent_id="wd-org-exec"),
        WDOrganization(id="wd-org-eng", name="Engineering", org_code="ENG", org_type="Department", parent_id="wd-org-exec"),
        WDOrganization(id="wd-org-fin", name="Finance", org_code="FIN", org_type="Department", parent_id="wd-org-exec"),
        WDOrganization(id="wd-org-procurement", name="Procurement", org_code="PROC", org_type="Cost Center", parent_id="wd-org-fin"),
    ]
    db.add_all(orgs)

    # Workers (matching CLM users where possible)
    workers = [
        WDWorker(id="wd-w1", employee_id="EMP001", first_name="Alex", last_name="Morgan",
                 email="admin@acmecorp.com", job_title="VP, Contract Management",
                 department="Legal", cost_center="CC-LEGAL-01", location="New York, NY",
                 hire_date=datetime(2020, 3, 15)),
        WDWorker(id="wd-w2", employee_id="EMP002", first_name="Jordan", last_name="Chen",
                 email="legal@acmecorp.com", job_title="Senior Legal Counsel",
                 department="Legal", cost_center="CC-LEGAL-01", manager_id="wd-w1",
                 location="New York, NY", hire_date=datetime(2021, 6, 1)),
        WDWorker(id="wd-w3", employee_id="EMP003", first_name="Sarah", last_name="Mitchell",
                 email="sarah.mitchell@acmecorp.com", job_title="VP Sales",
                 department="Sales", cost_center="CC-SALES-01", location="San Francisco, CA",
                 hire_date=datetime(2019, 8, 20)),
        WDWorker(id="wd-w4", employee_id="EMP004", first_name="Emily", last_name="Chen",
                 email="emily.chen@acmecorp.com", job_title="Customer Success Manager",
                 department="Customer Success", cost_center="CC-CS-01", manager_id="wd-w3",
                 location="San Francisco, CA", hire_date=datetime(2022, 1, 10)),
        WDWorker(id="wd-w5", employee_id="EMP005", first_name="James", last_name="Rodriguez",
                 email="james.rodriguez@acmecorp.com", job_title="Account Executive",
                 department="Sales", cost_center="CC-SALES-01", manager_id="wd-w3",
                 location="Chicago, IL", hire_date=datetime(2021, 11, 1)),
        WDWorker(id="wd-w6", employee_id="EMP006", first_name="Rachel", last_name="Kim",
                 email="rachel.kim@acmecorp.com", job_title="CFO",
                 department="Finance", cost_center="CC-FIN-01", location="New York, NY",
                 hire_date=datetime(2018, 4, 1)),
        WDWorker(id="wd-w7", employee_id="EMP007", first_name="Tom", last_name="Nguyen",
                 email="tom.nguyen@acmecorp.com", job_title="Procurement Manager",
                 department="Procurement", cost_center="CC-PROC-01", manager_id="wd-w6",
                 location="New York, NY", hire_date=datetime(2022, 7, 15)),
        WDWorker(id="wd-w8", employee_id="EMP008", first_name="Priya", last_name="Sharma",
                 email="priya.sharma@acmecorp.com", job_title="CTO",
                 department="Engineering", cost_center="CC-ENG-01", location="Austin, TX",
                 hire_date=datetime(2019, 1, 2)),
    ]
    db.add_all(workers)

    # Positions
    positions = [
        WDPosition(position_id="POS-001", title="VP, Contract Management", organization_id="wd-org-legal", worker_id="wd-w1", job_family="Legal"),
        WDPosition(position_id="POS-002", title="Senior Legal Counsel", organization_id="wd-org-legal", worker_id="wd-w2", job_family="Legal"),
        WDPosition(position_id="POS-003", title="VP Sales", organization_id="wd-org-sales", worker_id="wd-w3", job_family="Sales"),
        WDPosition(position_id="POS-004", title="Customer Success Manager", organization_id="wd-org-cs", worker_id="wd-w4", job_family="Customer Success"),
        WDPosition(position_id="POS-005", title="Account Executive", organization_id="wd-org-sales", worker_id="wd-w5", job_family="Sales"),
        WDPosition(position_id="POS-006", title="CFO", organization_id="wd-org-fin", worker_id="wd-w6", job_family="Finance"),
        WDPosition(position_id="POS-007", title="Procurement Manager", organization_id="wd-org-procurement", worker_id="wd-w7", job_family="Procurement"),
        WDPosition(position_id="POS-008", title="CTO", organization_id="wd-org-eng", worker_id="wd-w8", job_family="Engineering"),
        WDPosition(position_id="POS-009", title="Contract Analyst", organization_id="wd-org-legal", worker_id=None, job_family="Legal", is_filled=False),
    ]
    db.add_all(positions)
    print("  Workday: 7 orgs, 8 workers, 9 positions")


# =============================================================================
# SAP
# =============================================================================

def _seed_sap(db):
    now = datetime.utcnow()

    # Purchase Orders tied to CLM contracts
    pos = [
        SAPPurchaseOrder(
            id="sap-po1", po_number="PO-2024-001", vendor_name="KR8 AI Inc.",
            vendor_code="V-KR8", description="AI Platform License - MSA Year 1",
            total_amount=2_500_000, status="Partially Invoiced",
            order_date=datetime(2024, 1, 15), delivery_date=datetime(2024, 2, 1),
            cost_center="CC-ENG-01", contract_reference="FOXO-KR8-MSA-2024",
        ),
        SAPPurchaseOrder(
            id="sap-po2", po_number="PO-2024-002", vendor_name="KR8 AI Inc.",
            vendor_code="V-KR8", description="SLA Management Addendum Services",
            total_amount=180_000, status="Open",
            order_date=datetime(2024, 6, 1), delivery_date=datetime(2024, 7, 1),
            cost_center="CC-ENG-01", contract_reference="FOXO-KR8-ADD1-2024",
        ),
        SAPPurchaseOrder(
            id="sap-po3", po_number="PO-2024-003", vendor_name="Initech Solutions",
            vendor_code="V-INIT", description="IT Infrastructure Support",
            total_amount=96_000, status="Fully Invoiced",
            order_date=datetime(2024, 3, 1), delivery_date=datetime(2024, 4, 1),
            cost_center="CC-ENG-01",
        ),
        SAPPurchaseOrder(
            id="sap-po4", po_number="PO-2025-001", vendor_name="Globex Corporation",
            vendor_code="V-GLOB", description="APAC Market Data License",
            total_amount=750_000, status="Open",
            order_date=datetime(2025, 1, 15), delivery_date=datetime(2025, 3, 1),
            cost_center="CC-SALES-01",
        ),
    ]
    db.add_all(pos)

    # Line items for KR8 AI PO
    items = [
        SAPPOLineItem(po_id="sap-po1", line_number=10, material_number="SW-AI-LIC",
                       description="AI Platform Enterprise License", quantity=1,
                       unit_price=2_000_000, total_price=2_000_000, delivery_date=datetime(2024, 2, 1)),
        SAPPOLineItem(po_id="sap-po1", line_number=20, material_number="SVC-IMPL",
                       description="Implementation Services", quantity=1,
                       unit_price=300_000, total_price=300_000, delivery_date=datetime(2024, 3, 1)),
        SAPPOLineItem(po_id="sap-po1", line_number=30, material_number="SVC-TRAIN",
                       description="Training (5 days)", quantity=5,
                       unit_price=40_000, total_price=200_000, delivery_date=datetime(2024, 4, 1)),
        SAPPOLineItem(po_id="sap-po2", line_number=10, material_number="SVC-SLA",
                       description="SLA Management Fee (monthly)", quantity=12,
                       unit_price=15_000, total_price=180_000, delivery_date=datetime(2024, 7, 1)),
    ]
    db.add_all(items)

    # Invoices
    invoices = [
        SAPInvoice(invoice_number="INV-2024-0001", po_id="sap-po1", vendor_name="KR8 AI Inc.",
                   invoice_date=datetime(2024, 2, 15), due_date=datetime(2024, 3, 15),
                   amount=2_000_000, status="Paid", payment_date=datetime(2024, 3, 10),
                   payment_reference="PAY-2024-001"),
        SAPInvoice(invoice_number="INV-2024-0002", po_id="sap-po1", vendor_name="KR8 AI Inc.",
                   invoice_date=datetime(2024, 3, 30), due_date=datetime(2024, 4, 30),
                   amount=300_000, status="Paid", payment_date=datetime(2024, 4, 25),
                   payment_reference="PAY-2024-002"),
        SAPInvoice(invoice_number="INV-2024-0003", po_id="sap-po2", vendor_name="KR8 AI Inc.",
                   invoice_date=datetime(2024, 7, 1), due_date=datetime(2024, 8, 1),
                   amount=45_000, status="Paid", payment_date=datetime(2024, 7, 28)),
        SAPInvoice(invoice_number="INV-2024-0004", po_id="sap-po2", vendor_name="KR8 AI Inc.",
                   invoice_date=datetime(2024, 10, 1), due_date=datetime(2024, 11, 1),
                   amount=45_000, status="Paid", payment_date=datetime(2024, 10, 30)),
        SAPInvoice(invoice_number="INV-2025-0001", po_id="sap-po2", vendor_name="KR8 AI Inc.",
                   invoice_date=datetime(2025, 1, 1), due_date=datetime(2025, 2, 1),
                   amount=45_000, status="Approved"),
        SAPInvoice(invoice_number="INV-2025-0002", po_id="sap-po2", vendor_name="KR8 AI Inc.",
                   invoice_date=datetime(2025, 4, 1), due_date=datetime(2025, 5, 1),
                   amount=45_000, status="Pending"),
        SAPInvoice(invoice_number="INV-2024-0010", po_id="sap-po3", vendor_name="Initech Solutions",
                   invoice_date=datetime(2024, 4, 1), due_date=datetime(2024, 5, 1),
                   amount=96_000, status="Paid", payment_date=datetime(2024, 4, 28)),
        SAPInvoice(invoice_number="INV-2025-0003", po_id="sap-po4", vendor_name="Globex Corporation",
                   invoice_date=datetime(2025, 3, 1), due_date=datetime(2025, 3, 15),
                   amount=375_000, status="Overdue"),
    ]
    db.add_all(invoices)

    # Payments
    payments = [
        SAPPayment(payment_number="PAY-2024-001", vendor_name="KR8 AI Inc.", vendor_code="V-KR8",
                   amount=2_000_000, payment_date=datetime(2024, 3, 10), payment_method="Wire",
                   bank_reference="WIR-2024-0342", invoice_references=["INV-2024-0001"]),
        SAPPayment(payment_number="PAY-2024-002", vendor_name="KR8 AI Inc.", vendor_code="V-KR8",
                   amount=300_000, payment_date=datetime(2024, 4, 25), payment_method="Wire",
                   bank_reference="WIR-2024-0518", invoice_references=["INV-2024-0002"]),
        SAPPayment(payment_number="PAY-2024-003", vendor_name="KR8 AI Inc.", vendor_code="V-KR8",
                   amount=90_000, payment_date=datetime(2024, 10, 30), payment_method="ACH",
                   bank_reference="ACH-2024-1842", invoice_references=["INV-2024-0003", "INV-2024-0004"]),
        SAPPayment(payment_number="PAY-2024-010", vendor_name="Initech Solutions", vendor_code="V-INIT",
                   amount=96_000, payment_date=datetime(2024, 4, 28), payment_method="ACH",
                   bank_reference="ACH-2024-0612", invoice_references=["INV-2024-0010"]),
    ]
    db.add_all(payments)
    print("  SAP: 4 POs, 4 line items, 8 invoices, 4 payments")


# =============================================================================
# ServiceNow
# =============================================================================

def _seed_servicenow(db):
    service = "KR8 AI Platform"

    # SLA Results - monthly measurements across 6 months
    sla_metrics = [
        ("Platform Availability", "availability", 99.9, "%", [99.95, 99.88, 99.97, 99.92, 99.85, 99.96]),
        ("API Response Time (p95)", "response_time", 200, "ms", [185, 210, 178, 195, 225, 188]),
        ("Critical Incident Response", "response_time", 15, "minutes", [8, 12, 22, 10, 14, 9]),
        ("Critical Incident Resolution", "resolution_time", 240, "minutes", [180, 320, 195, 210, 280, 175]),
        ("Data Processing Throughput", "throughput", 1000, "records/sec", [1150, 1080, 1200, 1100, 950, 1175]),
        ("Backup Recovery Time", "resolution_time", 60, "minutes", [35, 42, 38, 55, 40, 33]),
    ]

    months = ["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"]

    for sla_name, metric_type, target, unit, actuals in sla_metrics:
        for i, month in enumerate(months):
            actual = actuals[i]
            # For response/resolution time, lower is better
            if metric_type in ("response_time", "resolution_time"):
                is_met = actual <= target
            else:
                is_met = actual >= target
            breach_count = 0 if is_met else random.randint(1, 3)
            credit = 0 if is_met else round(random.uniform(500, 5000), 2)

            db.add(SNOWSLAResult(
                sla_name=sla_name, service_name=service, metric_type=metric_type,
                target_value=target, actual_value=actual, unit=unit, is_met=is_met,
                measurement_period=month, measurement_date=datetime.strptime(f"{month}-28", "%Y-%m-%d"),
                breach_count=breach_count, credit_amount=credit,
                notes=None if is_met else f"SLA breach: actual {actual}{unit} vs target {target}{unit}",
            ))

    # Incidents
    inc_data = [
        ("INC0045231", "API gateway timeout during peak load", "P2", "2-High", "Resolved",
         "API", datetime(2024, 10, 15, 9, 30), 12, 180, False),
        ("INC0045342", "Critical: Data pipeline processing failure", "P1", "1-Critical", "Resolved",
         "Data Pipeline", datetime(2024, 11, 3, 2, 15), 5, 320, True),
        ("INC0045567", "Intermittent authentication failures", "P3", "3-Medium", "Resolved",
         "Authentication", datetime(2024, 12, 8, 14, 0), 25, 90, False),
        ("INC0045890", "Dashboard rendering slow (>5s)", "P4", "4-Low", "Resolved",
         "Frontend", datetime(2025, 1, 12, 10, 0), 45, 240, False),
        ("INC0046012", "Critical: Database connection pool exhaustion", "P1", "1-Critical", "Resolved",
         "Database", datetime(2025, 2, 5, 3, 45), 8, 280, True),
        ("INC0046234", "SSL certificate renewal failure", "P2", "2-High", "Resolved",
         "Infrastructure", datetime(2025, 2, 20, 11, 30), 15, 120, False),
        ("INC0046456", "Memory leak in ML inference service", "P3", "3-Medium", "In Progress",
         "ML Engine", datetime(2025, 3, 15, 16, 0), 30, None, False),
        ("INC0046567", "Scheduled maintenance notification failure", "P4", "4-Low", "New",
         "Notifications", datetime(2025, 3, 25, 8, 0), None, None, False),
    ]
    for num, desc, priority, severity, state, cat, opened, resp_min, res_min, breached in inc_data:
        resolved = opened + timedelta(minutes=res_min) if res_min else None
        db.add(SNOWIncident(
            number=num, short_description=desc, description=f"Detailed: {desc}",
            priority=priority, severity=severity, state=state, category=cat,
            service_name=service, assigned_to="Platform Engineering",
            assignment_group="KR8 AI Support", opened_at=opened,
            resolved_at=resolved, closed_at=resolved,
            response_time_minutes=resp_min, resolution_time_minutes=res_min,
            sla_breached=breached,
        ))

    # Change Requests
    changes = [
        ("CHG0012001", "Upgrade ML model to v3.2", "Standard", "Low", "Closed",
         datetime(2024, 11, 1), datetime(2024, 11, 2), True),
        ("CHG0012045", "Database connection pool tuning", "Normal", "Medium", "Closed",
         datetime(2025, 2, 8), datetime(2025, 2, 9), True),
        ("CHG0012089", "API gateway rate limiting update", "Normal", "Low", "Closed",
         datetime(2025, 3, 1), datetime(2025, 3, 2), True),
        ("CHG0012123", "Infrastructure scaling for Q2 load", "Normal", "Medium", "Scheduled",
         datetime(2025, 4, 5), datetime(2025, 4, 6), None),
    ]
    for num, desc, ctype, risk, state, start, end, success in changes:
        actual_start = start if state == "Closed" else None
        actual_end = end if state == "Closed" else None
        db.add(SNOWChangeRequest(
            number=num, short_description=desc, description=f"Detailed: {desc}",
            change_type=ctype, risk=risk, state=state, service_name=service,
            requested_by="Platform Engineering", assigned_to="KR8 AI DevOps",
            planned_start=start, planned_end=end,
            actual_start=actual_start, actual_end=actual_end, success=success,
        ))

    print("  ServiceNow: 36 SLA results, 8 incidents, 4 change requests")


# =============================================================================
# Qualtrics
# =============================================================================

def _seed_qualtrics(db):
    # Survey templates
    surveys = [
        QSurvey(id="q-srv1", name="Quarterly Relationship Health Assessment",
                description="External partner perception survey for business relationship KPIs",
                survey_type="RelationshipHealth", question_count=12, response_count=0),
        QSurvey(id="q-srv2", name="Annual Satisfaction Survey",
                description="Comprehensive satisfaction survey for key accounts",
                survey_type="Satisfaction", question_count=20, response_count=0),
        QSurvey(id="q-srv3", name="Net Promoter Score Survey",
                description="Quick NPS pulse check", survey_type="NPS", question_count=3, response_count=0),
    ]
    db.add_all(surveys)

    # Responses — external perception data for KR8 AI relationship
    # These map to CLM KPIs: Platform Availability, Incident Resolution, Response Time,
    # Data Processing Accuracy (Structured + Unstructured)
    quarters = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2025-Q1", "2025-Q2"]
    kr8_respondents = [
        ("David Park", "david.park@kr8ai.com", "KR8 AI Inc."),
        ("Lisa Wang", "lisa.wang@kr8ai.com", "KR8 AI Inc."),
    ]

    for period in quarters:
        year = int(period[:4])
        quarter = int(period[-1])
        base_date = datetime(year, quarter * 3, 15)

        for name, email, company in kr8_respondents:
            # Scores that match the perception score pattern seeded in CLM
            # Q2 2024 was the dip, then recovery
            base_scores = {
                "2024-Q1": {"availability": 8.5, "incident_response": 7.8, "response_time": 7.5,
                            "accuracy_structured": 9.0, "accuracy_unstructured": 7.2, "communication": 7.8},
                "2024-Q2": {"availability": 7.8, "incident_response": 7.0, "response_time": 6.8,
                            "accuracy_structured": 8.8, "accuracy_unstructured": 6.5, "communication": 6.5},
                "2024-Q3": {"availability": 8.8, "incident_response": 7.5, "response_time": 7.2,
                            "accuracy_structured": 9.2, "accuracy_unstructured": 7.0, "communication": 7.5},
                "2024-Q4": {"availability": 8.2, "incident_response": 7.2, "response_time": 7.0,
                            "accuracy_structured": 8.8, "accuracy_unstructured": 6.8, "communication": 7.0},
                "2025-Q1": {"availability": 8.0, "incident_response": 7.3, "response_time": 6.8,
                            "accuracy_structured": 9.0, "accuracy_unstructured": 6.5, "communication": 7.2},
                "2025-Q2": {"availability": 8.6, "incident_response": 7.8, "response_time": 7.5,
                            "accuracy_structured": 9.0, "accuracy_unstructured": 7.0, "communication": 7.8},
            }

            scores = base_scores[period]
            # Add small random variance per respondent
            jittered = {k: round(min(10, max(1, v + random.uniform(-0.3, 0.3))), 1) for k, v in scores.items()}
            jittered["overall_satisfaction"] = round(sum(jittered.values()) / len(jittered), 1)
            jittered["would_recommend"] = 8 if jittered["overall_satisfaction"] > 7.5 else 6

            db.add(QResponse(
                survey_id="q-srv1", respondent_email=email, respondent_name=name,
                respondent_company=company, relationship_name="Acme Corp - KR8 AI",
                period=period, submitted_at=base_date + timedelta(days=random.randint(0, 5)),
                duration_seconds=random.randint(300, 600),
                answers=jittered,
            ))

    # Update response counts
    for survey in surveys:
        survey.response_count = db.query(QResponse).filter(QResponse.survey_id == survey.id).count()

    print(f"  Qualtrics: 3 surveys, {len(quarters) * len(kr8_respondents)} responses")


# =============================================================================
# Datadog
# =============================================================================

def _seed_datadog(db):
    # Services (KR8 AI platform components)
    services = [
        DDService(id="dd-svc-api", name="kr8-api-gateway", environment="production",
                  service_type="api", team="Platform Engineering", language="Go"),
        DDService(id="dd-svc-ml", name="kr8-ml-inference", environment="production",
                  service_type="api", team="ML Engineering", language="Python"),
        DDService(id="dd-svc-data", name="kr8-data-pipeline", environment="production",
                  service_type="queue", team="Data Engineering", language="Python"),
        DDService(id="dd-svc-web", name="kr8-web-app", environment="production",
                  service_type="web", team="Frontend Engineering", language="TypeScript"),
        DDService(id="dd-svc-db", name="kr8-postgres-primary", environment="production",
                  service_type="database", team="Platform Engineering", language="N/A"),
    ]
    db.add_all(services)

    # SLOs
    slos = [
        DDSLO(name="API Gateway Availability", description="99.9% availability for API gateway",
              service_id="dd-svc-api", slo_type="monitor", target_percentage=99.9,
              timeframe="30d", current_percentage=99.95, status="OK", error_budget_remaining=50.0),
        DDSLO(name="API Response Time p95 < 200ms", description="95th percentile response time under 200ms",
              service_id="dd-svc-api", slo_type="metric", target_percentage=99.0,
              timeframe="30d", current_percentage=98.2, status="Warning", error_budget_remaining=12.0),
        DDSLO(name="ML Inference Latency p99 < 500ms", description="99th percentile ML inference under 500ms",
              service_id="dd-svc-ml", slo_type="metric", target_percentage=99.5,
              timeframe="30d", current_percentage=99.7, status="OK", error_budget_remaining=65.0),
        DDSLO(name="Data Pipeline Success Rate", description="99.5% pipeline execution success",
              service_id="dd-svc-data", slo_type="metric", target_percentage=99.5,
              timeframe="30d", current_percentage=99.8, status="OK", error_budget_remaining=60.0),
        DDSLO(name="Database Availability", description="99.99% database uptime",
              service_id="dd-svc-db", slo_type="monitor", target_percentage=99.99,
              timeframe="30d", current_percentage=99.98, status="Warning", error_budget_remaining=8.0),
        DDSLO(name="Web App Error Rate < 1%", description="Less than 1% error rate on web app",
              service_id="dd-svc-web", slo_type="metric", target_percentage=99.0,
              timeframe="30d", current_percentage=99.6, status="OK", error_budget_remaining=40.0),
    ]
    db.add_all(slos)

    # Monitor Status
    monitors = [
        DDMonitorStatus(monitor_name="API Gateway Health", service_id="dd-svc-api",
                        monitor_type="synthetics", status="OK", value=99.95, threshold=99.9),
        DDMonitorStatus(monitor_name="API p95 Latency", service_id="dd-svc-api",
                        monitor_type="metric", status="Warn", value=210, threshold=200,
                        message="p95 latency slightly above 200ms threshold"),
        DDMonitorStatus(monitor_name="ML Inference Queue Depth", service_id="dd-svc-ml",
                        monitor_type="metric", status="OK", value=12, threshold=100),
        DDMonitorStatus(monitor_name="Data Pipeline Lag", service_id="dd-svc-data",
                        monitor_type="metric", status="OK", value=45, threshold=300,
                        message="Pipeline processing lag in seconds"),
        DDMonitorStatus(monitor_name="Database Connection Pool", service_id="dd-svc-db",
                        monitor_type="metric", status="OK", value=35, threshold=80,
                        message="Active connections out of 80 max"),
        DDMonitorStatus(monitor_name="Database Replication Lag", service_id="dd-svc-db",
                        monitor_type="metric", status="OK", value=0.5, threshold=10,
                        message="Replication lag in seconds"),
        DDMonitorStatus(monitor_name="Web App Error Rate", service_id="dd-svc-web",
                        monitor_type="apm", status="OK", value=0.4, threshold=1.0),
        DDMonitorStatus(monitor_name="SSL Certificate Expiry", service_id="dd-svc-api",
                        monitor_type="synthetics", status="OK", value=45, threshold=14,
                        message="Days until SSL cert expiry"),
    ]
    db.add_all(monitors)

    # Incidents
    now = datetime.utcnow()
    incidents = [
        DDIncident(title="API Gateway 503 Errors During Peak", severity="SEV-2", status="Resolved",
                   service_id="dd-svc-api", commander="Alex Morgan",
                   created_at=datetime(2024, 10, 15, 9, 30), resolved_at=datetime(2024, 10, 15, 12, 30),
                   duration_minutes=180, customer_impact=True,
                   postmortem_url="https://wiki.internal/postmortem/2024-10-api-503"),
        DDIncident(title="Data Pipeline Complete Failure", severity="SEV-1", status="Resolved",
                   service_id="dd-svc-data", commander="Priya Sharma",
                   created_at=datetime(2024, 11, 3, 2, 15), resolved_at=datetime(2024, 11, 3, 7, 35),
                   duration_minutes=320, customer_impact=True,
                   postmortem_url="https://wiki.internal/postmortem/2024-11-pipeline-failure"),
        DDIncident(title="Database Connection Pool Exhaustion", severity="SEV-1", status="Resolved",
                   service_id="dd-svc-db", commander="Alex Morgan",
                   created_at=datetime(2025, 2, 5, 3, 45), resolved_at=datetime(2025, 2, 5, 8, 25),
                   duration_minutes=280, customer_impact=True,
                   postmortem_url="https://wiki.internal/postmortem/2025-02-db-pool"),
        DDIncident(title="ML Inference Memory Leak", severity="SEV-3", status="Active",
                   service_id="dd-svc-ml", commander="Priya Sharma",
                   created_at=datetime(2025, 3, 15, 16, 0),
                   customer_impact=False),
    ]
    db.add_all(incidents)
    print("  Datadog: 5 services, 6 SLOs, 8 monitors, 4 incidents")


def main():
    print("Seeding mock enterprise systems...")
    seed_all()
    print("\nDone! Run: uvicorn app.main:app --port 9000 --reload")


if __name__ == "__main__":
    main()
