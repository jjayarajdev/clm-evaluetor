"""SQLAlchemy models for all mock enterprise systems."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db import Base


def gen_id() -> str:
    return str(uuid.uuid4())


# =============================================================================
# Salesforce Models
# =============================================================================

class SFAccount(Base):
    """Salesforce Account (maps to CLM Organization)."""
    __tablename__ = "sf_accounts"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    account_number = Column(String, unique=True)
    account_type = Column(String)  # Customer, Partner, Vendor
    industry = Column(String)
    annual_revenue = Column(Float)
    number_of_employees = Column(Integer)
    billing_city = Column(String)
    billing_state = Column(String)
    billing_country = Column(String)
    website = Column(String)
    phone = Column(String)
    owner_id = Column(String, ForeignKey("sf_users.id"))
    status = Column(String, default="Active")
    created_date = Column(DateTime, default=datetime.utcnow)
    last_modified_date = Column(DateTime, default=datetime.utcnow)

    contacts = relationship("SFContact", back_populates="account")
    opportunities = relationship("SFOpportunity", back_populates="account")


class SFContact(Base):
    """Salesforce Contact (maps to CLM Org Officers / Team Members)."""
    __tablename__ = "sf_contacts"

    id = Column(String, primary_key=True, default=gen_id)
    account_id = Column(String, ForeignKey("sf_accounts.id"))
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    phone = Column(String)
    title = Column(String)
    department = Column(String)
    is_primary = Column(Boolean, default=False)
    created_date = Column(DateTime, default=datetime.utcnow)

    account = relationship("SFAccount", back_populates="contacts")


class SFOpportunity(Base):
    """Salesforce Opportunity (maps to CLM contract renewals/pipeline)."""
    __tablename__ = "sf_opportunities"

    id = Column(String, primary_key=True, default=gen_id)
    account_id = Column(String, ForeignKey("sf_accounts.id"))
    name = Column(String, nullable=False)
    stage = Column(String)  # Prospecting, Qualification, Proposal, Negotiation, Closed Won, Closed Lost
    amount = Column(Float)
    currency = Column(String, default="USD")
    close_date = Column(DateTime)
    probability = Column(Integer)
    contract_type = Column(String)  # New, Renewal, Amendment
    owner_id = Column(String, ForeignKey("sf_users.id"))
    description = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)

    account = relationship("SFAccount", back_populates="opportunities")


class SFUser(Base):
    """Salesforce User (account owners, opportunity owners)."""
    __tablename__ = "sf_users"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String)
    email = Column(String)
    role = Column(String)
    department = Column(String)
    is_active = Column(Boolean, default=True)


# =============================================================================
# Workday Models
# =============================================================================

class WDWorker(Base):
    """Workday Worker (employee data for team members)."""
    __tablename__ = "wd_workers"

    id = Column(String, primary_key=True, default=gen_id)
    employee_id = Column(String, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    job_title = Column(String)
    department = Column(String)
    cost_center = Column(String)
    manager_id = Column(String, ForeignKey("wd_workers.id"), nullable=True)
    location = Column(String)
    hire_date = Column(DateTime)
    status = Column(String, default="Active")  # Active, On Leave, Terminated
    worker_type = Column(String, default="Employee")  # Employee, Contractor, Contingent

    direct_reports = relationship("WDWorker", foreign_keys=[manager_id])


class WDOrganization(Base):
    """Workday Supervisory Organization (maps to CLM Business Units)."""
    __tablename__ = "wd_organizations"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    org_code = Column(String, unique=True)
    org_type = Column(String)  # Department, Division, Cost Center
    parent_id = Column(String, ForeignKey("wd_organizations.id"), nullable=True)
    manager_id = Column(String, ForeignKey("wd_workers.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    children = relationship("WDOrganization", foreign_keys=[parent_id])


class WDPosition(Base):
    """Workday Position (role assignments)."""
    __tablename__ = "wd_positions"

    id = Column(String, primary_key=True, default=gen_id)
    position_id = Column(String, unique=True)
    title = Column(String)
    organization_id = Column(String, ForeignKey("wd_organizations.id"))
    worker_id = Column(String, ForeignKey("wd_workers.id"), nullable=True)
    job_family = Column(String)
    is_filled = Column(Boolean, default=True)


# =============================================================================
# SAP Models
# =============================================================================

class SAPPurchaseOrder(Base):
    """SAP Purchase Order (maps to CLM contract financials)."""
    __tablename__ = "sap_purchase_orders"

    id = Column(String, primary_key=True, default=gen_id)
    po_number = Column(String, unique=True)
    vendor_name = Column(String)
    vendor_code = Column(String)
    description = Column(Text)
    total_amount = Column(Float)
    currency = Column(String, default="USD")
    status = Column(String)  # Open, Partially Invoiced, Fully Invoiced, Closed
    order_date = Column(DateTime)
    delivery_date = Column(DateTime)
    cost_center = Column(String)
    contract_reference = Column(String)  # Link back to CLM contract
    created_at = Column(DateTime, default=datetime.utcnow)

    line_items = relationship("SAPPOLineItem", back_populates="purchase_order")
    invoices = relationship("SAPInvoice", back_populates="purchase_order")


class SAPPOLineItem(Base):
    """SAP PO Line Item."""
    __tablename__ = "sap_po_line_items"

    id = Column(String, primary_key=True, default=gen_id)
    po_id = Column(String, ForeignKey("sap_purchase_orders.id"))
    line_number = Column(Integer)
    material_number = Column(String)
    description = Column(String)
    quantity = Column(Float)
    unit_price = Column(Float)
    total_price = Column(Float)
    delivery_date = Column(DateTime)

    purchase_order = relationship("SAPPurchaseOrder", back_populates="line_items")


class SAPInvoice(Base):
    """SAP Invoice (payment tracking for obligation compliance)."""
    __tablename__ = "sap_invoices"

    id = Column(String, primary_key=True, default=gen_id)
    invoice_number = Column(String, unique=True)
    po_id = Column(String, ForeignKey("sap_purchase_orders.id"))
    vendor_name = Column(String)
    invoice_date = Column(DateTime)
    due_date = Column(DateTime)
    amount = Column(Float)
    currency = Column(String, default="USD")
    status = Column(String)  # Pending, Approved, Paid, Overdue, Disputed
    payment_date = Column(DateTime, nullable=True)
    payment_reference = Column(String, nullable=True)

    purchase_order = relationship("SAPPurchaseOrder", back_populates="invoices")


class SAPPayment(Base):
    """SAP Payment run result."""
    __tablename__ = "sap_payments"

    id = Column(String, primary_key=True, default=gen_id)
    payment_number = Column(String, unique=True)
    vendor_name = Column(String)
    vendor_code = Column(String)
    amount = Column(Float)
    currency = Column(String, default="USD")
    payment_date = Column(DateTime)
    payment_method = Column(String)  # Wire, ACH, Check
    bank_reference = Column(String)
    invoice_references = Column(JSON)  # List of invoice numbers


# =============================================================================
# ServiceNow Models
# =============================================================================

class SNOWSLAResult(Base):
    """ServiceNow SLA measurement result."""
    __tablename__ = "snow_sla_results"

    id = Column(String, primary_key=True, default=gen_id)
    sla_name = Column(String)
    service_name = Column(String)
    metric_type = Column(String)  # availability, response_time, resolution_time, throughput
    target_value = Column(Float)
    actual_value = Column(Float)
    unit = Column(String)  # percent, ms, hours, requests_per_second
    is_met = Column(Boolean)
    measurement_period = Column(String)  # 2026-03, 2026-Q1
    measurement_date = Column(DateTime)
    breach_count = Column(Integer, default=0)
    credit_amount = Column(Float, default=0)
    notes = Column(Text)


class SNOWIncident(Base):
    """ServiceNow Incident."""
    __tablename__ = "snow_incidents"

    id = Column(String, primary_key=True, default=gen_id)
    number = Column(String, unique=True)  # INC0012345
    short_description = Column(String)
    description = Column(Text)
    priority = Column(String)  # P1, P2, P3, P4
    severity = Column(String)  # 1-Critical, 2-High, 3-Medium, 4-Low
    state = Column(String)  # New, In Progress, On Hold, Resolved, Closed
    category = Column(String)
    service_name = Column(String)
    assigned_to = Column(String)
    assignment_group = Column(String)
    opened_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    response_time_minutes = Column(Integer)
    resolution_time_minutes = Column(Integer, nullable=True)
    sla_breached = Column(Boolean, default=False)


class SNOWChangeRequest(Base):
    """ServiceNow Change Request."""
    __tablename__ = "snow_change_requests"

    id = Column(String, primary_key=True, default=gen_id)
    number = Column(String, unique=True)  # CHG0012345
    short_description = Column(String)
    description = Column(Text)
    change_type = Column(String)  # Standard, Normal, Emergency
    risk = Column(String)  # Low, Medium, High
    state = Column(String)  # New, Assess, Authorize, Scheduled, Implement, Review, Closed
    service_name = Column(String)
    requested_by = Column(String)
    assigned_to = Column(String)
    planned_start = Column(DateTime)
    planned_end = Column(DateTime)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    success = Column(Boolean, nullable=True)


# =============================================================================
# Qualtrics Models
# =============================================================================

class QSurvey(Base):
    """Qualtrics Survey definition."""
    __tablename__ = "q_surveys"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String)
    description = Column(Text)
    survey_type = Column(String)  # RelationshipHealth, Satisfaction, NPS
    status = Column(String, default="Active")  # Active, Closed, Draft
    created_date = Column(DateTime, default=datetime.utcnow)
    last_modified = Column(DateTime, default=datetime.utcnow)
    question_count = Column(Integer, default=0)
    response_count = Column(Integer, default=0)

    responses = relationship("QResponse", back_populates="survey")


class QResponse(Base):
    """Qualtrics Survey Response (external perception data)."""
    __tablename__ = "q_responses"

    id = Column(String, primary_key=True, default=gen_id)
    survey_id = Column(String, ForeignKey("q_surveys.id"))
    respondent_email = Column(String)
    respondent_name = Column(String)
    respondent_company = Column(String)
    relationship_name = Column(String)  # Links to CLM relationship
    period = Column(String)  # 2026-Q1
    submitted_at = Column(DateTime)
    duration_seconds = Column(Integer)
    answers = Column(JSON)  # {"q1": 8, "q2": 7, "q3": "Good communication", ...}

    survey = relationship("QSurvey", back_populates="responses")


# =============================================================================
# Datadog Models
# =============================================================================

class DDService(Base):
    """Datadog monitored service."""
    __tablename__ = "dd_services"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, unique=True)
    environment = Column(String, default="production")
    service_type = Column(String)  # web, api, database, queue
    team = Column(String)
    language = Column(String)


class DDSLO(Base):
    """Datadog SLO (Service Level Objective)."""
    __tablename__ = "dd_slos"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String)
    description = Column(Text)
    service_id = Column(String, ForeignKey("dd_services.id"))
    slo_type = Column(String)  # metric, monitor
    target_percentage = Column(Float)  # e.g., 99.9
    timeframe = Column(String)  # 7d, 30d, 90d
    current_percentage = Column(Float)
    status = Column(String)  # OK, Warning, Breached
    error_budget_remaining = Column(Float)  # percentage
    last_updated = Column(DateTime, default=datetime.utcnow)


class DDMonitorStatus(Base):
    """Datadog Monitor check result."""
    __tablename__ = "dd_monitor_status"

    id = Column(String, primary_key=True, default=gen_id)
    monitor_name = Column(String)
    service_id = Column(String, ForeignKey("dd_services.id"))
    monitor_type = Column(String)  # metric, apm, synthetics, log
    status = Column(String)  # OK, Warn, Alert, No Data
    value = Column(Float)
    threshold = Column(Float)
    message = Column(Text)
    last_triggered = Column(DateTime, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)


class DDIncident(Base):
    """Datadog Incident (PagerDuty-style)."""
    __tablename__ = "dd_incidents"

    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String)
    severity = Column(String)  # SEV-1, SEV-2, SEV-3, SEV-4
    status = Column(String)  # Active, Stable, Resolved
    service_id = Column(String, ForeignKey("dd_services.id"))
    commander = Column(String)
    created_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    customer_impact = Column(Boolean, default=False)
    postmortem_url = Column(String, nullable=True)
