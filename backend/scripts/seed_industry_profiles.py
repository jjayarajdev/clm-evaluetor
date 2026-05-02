"""Seed industry profiles for multi-domain CLM support.

Creates three profiles:
  - IT Services (codifies current platform behavior)
  - Manufacturing (supply chain, quality, procurement focus)
  - Pharma / Life Sciences (regulatory, GMP, clinical focus)

Run with: cd backend && uv run python -m scripts.seed_industry_profiles
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session_maker
from app.models.industry_profile import IndustryProfile


# =============================================================================
# IT SERVICES PROFILE (codifies current hardcoded behavior)
# =============================================================================

IT_SERVICES = {
    "name": "IT Services",
    "slug": "it-services",
    "description": "Technology, SaaS, professional services, and IT outsourcing contracts.",
    "contract_types": [
        {"code": "nda", "label": "NDA", "description": "Non-Disclosure Agreement"},
        {"code": "msa", "label": "MSA", "description": "Master Service Agreement"},
        {"code": "sow", "label": "SOW", "description": "Statement of Work"},
        {"code": "amendment", "label": "Amendment", "description": "Contract Amendment"},
        {"code": "vendor_agreement", "label": "Vendor Agreement", "description": "Vendor/Supplier Agreement"},
        {"code": "employment_contract", "label": "Employment", "description": "Employment Contract"},
        {"code": "license", "label": "License", "description": "Software/IP License Agreement"},
        {"code": "lease", "label": "Lease", "description": "Equipment or Facility Lease"},
    ],
    "clause_types": [
        {"code": "termination", "label": "Termination", "category": "general", "risk_weight": 10},
        {"code": "limitation_of_liability", "label": "Limitation of Liability", "category": "risk", "risk_weight": 15},
        {"code": "indemnification", "label": "Indemnification", "category": "risk", "risk_weight": 12},
        {"code": "confidentiality", "label": "Confidentiality", "category": "general", "risk_weight": 8},
        {"code": "ip", "label": "Intellectual Property", "category": "risk", "risk_weight": 12},
        {"code": "data_protection", "label": "Data Protection", "category": "compliance", "risk_weight": 10},
        {"code": "payment_terms", "label": "Payment Terms", "category": "commercial", "risk_weight": 5},
        {"code": "warranty", "label": "Warranty", "category": "general", "risk_weight": 8},
        {"code": "force_majeure", "label": "Force Majeure", "category": "general", "risk_weight": 5},
        {"code": "non_compete", "label": "Non-Compete", "category": "restriction", "risk_weight": 8},
        {"code": "non_solicitation", "label": "Non-Solicitation", "category": "restriction", "risk_weight": 6},
        {"code": "dispute_resolution", "label": "Dispute Resolution", "category": "general", "risk_weight": 5},
        {"code": "governing_law", "label": "Governing Law", "category": "general", "risk_weight": 3},
        {"code": "assignment", "label": "Assignment", "category": "general", "risk_weight": 5},
        {"code": "auto_renewal", "label": "Auto-Renewal", "category": "commercial", "risk_weight": 10},
        {"code": "sla", "label": "Service Level Agreement", "category": "operational", "risk_weight": 8},
        {"code": "service_description", "label": "Service Description", "category": "operational", "risk_weight": 3},
        {"code": "security", "label": "Security Requirements", "category": "compliance", "risk_weight": 10},
        {"code": "transition", "label": "Transition/Exit", "category": "operational", "risk_weight": 8},
    ],
    "risk_categories": [
        {"code": "unlimited_liability", "label": "Unlimited Liability", "severity": "high", "weight": 15, "description": "No cap on liability exposure"},
        {"code": "broad_indemnification", "label": "Broad Indemnification", "severity": "high", "weight": 12, "description": "Overly broad indemnification obligations"},
        {"code": "weak_termination", "label": "Weak Termination Rights", "severity": "medium", "weight": 10, "description": "Limited ability to terminate the agreement"},
        {"code": "auto_renewal_trap", "label": "Auto-Renewal Trap", "severity": "medium", "weight": 10, "description": "Auto-renewal with short notice window"},
        {"code": "unfavorable_ip", "label": "Unfavorable IP Terms", "severity": "high", "weight": 12, "description": "IP ownership terms that disadvantage one party"},
        {"code": "weak_confidentiality", "label": "Weak Confidentiality", "severity": "medium", "weight": 8, "description": "Inadequate confidentiality protections"},
        {"code": "missing_limitation", "label": "Missing Liability Cap", "severity": "high", "weight": 15, "description": "No limitation of liability clause found"},
        {"code": "one_sided_terms", "label": "One-Sided Terms", "severity": "high", "weight": 10, "description": "Terms that heavily favor one party"},
        {"code": "regulatory_risk", "label": "Regulatory Risk", "severity": "medium", "weight": 8, "description": "Potential regulatory compliance issues"},
        {"code": "ambiguous_language", "label": "Ambiguous Language", "severity": "low", "weight": 5, "description": "Vague or unclear contract language"},
    ],
    "sla_metrics": [
        {"code": "uptime_percentage", "label": "Uptime", "unit": "percentage", "direction": "higher_is_better", "default_target": 99.9},
        {"code": "response_time", "label": "Response Time", "unit": "hours", "direction": "lower_is_better", "default_target": 4},
        {"code": "resolution_time", "label": "Resolution Time", "unit": "hours", "direction": "lower_is_better", "default_target": 24},
        {"code": "availability", "label": "Availability", "unit": "percentage", "direction": "higher_is_better", "default_target": 99.5},
        {"code": "throughput", "label": "Throughput", "unit": "count", "direction": "higher_is_better"},
        {"code": "error_rate", "label": "Error Rate", "unit": "percentage", "direction": "lower_is_better", "default_target": 0.1},
    ],
    "field_definitions": {
        "_default": [
            {"section": "Key Terms", "fields": [
                {"key": "effective_date", "label": "Effective Date", "type": "date"},
                {"key": "expiration_date", "label": "Expiration Date", "type": "date"},
                {"key": "contract_value", "label": "Contract Value", "type": "currency"},
                {"key": "governing_law", "label": "Governing Law", "type": "text"},
                {"key": "auto_renewal", "label": "Auto-Renewal", "type": "boolean"},
                {"key": "notice_period_days", "label": "Notice Period", "type": "number", "suffix": "days"},
            ]},
            {"section": "Parties", "fields": [
                {"key": "counterparty", "label": "Counterparty", "type": "text"},
                {"key": "party_role", "label": "Our Role", "type": "text"},
            ]},
            {"section": "Liability & Risk", "fields": [
                {"key": "liability_cap_type", "label": "Liability Cap Type", "type": "text"},
                {"key": "liability_cap_amount", "label": "Liability Cap Amount", "type": "currency"},
                {"key": "dispute_resolution_method", "label": "Dispute Resolution", "type": "text"},
            ]},
        ],
    },
    "extraction_hints": {
        "metadata": "Extract standard contract metadata: parties, dates, value, governing law, renewal terms.",
        "clauses": "Focus on: termination, limitation of liability, indemnification, confidentiality, IP ownership, data protection, SLA, auto-renewal.",
        "risks": "Evaluate: unlimited liability, broad indemnification, weak termination, auto-renewal traps, unfavorable IP, missing limitation clauses.",
        "slas": "Look for: uptime percentages, response/resolution times, availability targets, penalty/credit structures.",
        "obligations": "Extract: reporting obligations, payment schedules, delivery milestones, compliance requirements, notification obligations.",
    },
    "ui_config": {
        "table_columns": [
            {"key": "filename", "label": "Contract Name", "width": 280},
            {"key": "contract_type", "label": "Type", "width": 100},
            {"key": "counterparty", "label": "Counterparty", "width": 180},
            {"key": "contract_value", "label": "Value", "format": "currency", "width": 120},
            {"key": "risk_level", "label": "Risk", "width": 80},
            {"key": "expiration_date", "label": "Expiry", "format": "date", "width": 100},
        ],
        "dashboard_widgets": [
            {"key": "total_contracts", "label": "Total Contracts", "color": "primary", "icon": "document"},
            {"key": "at_risk", "label": "At Risk", "color": "danger", "icon": "warning"},
            {"key": "compliance_rate", "label": "Compliance", "color": "success", "icon": "check", "format": "percentage"},
            {"key": "total_value", "label": "Contract Value", "color": "blue", "icon": "currency", "format": "currency"},
            {"key": "obligation_rate", "label": "Obligations", "color": "warning", "icon": "scale", "format": "percentage"},
            {"key": "sla_rate", "label": "SLA Performance", "color": "success", "icon": "chart", "format": "percentage"},
        ],
        "detail_tabs": [
            {"id": "overview", "label": "Overview", "icon": "document"},
            {"id": "review", "label": "Review", "icon": "eye"},
            {"id": "slas", "label": "SLAs", "icon": "chart"},
            {"id": "related", "label": "Related Docs", "icon": "link"},
            {"id": "documents", "label": "Documents", "icon": "folder"},
            {"id": "sharing", "label": "Sharing", "icon": "share"},
        ],
        "filters": ["contract_type", "risk_level", "status", "business_unit"],
        "labels": {
            "counterparty": "Counterparty",
            "contract_value": "Contract Value",
            "portfolio": "Portfolio Overview",
        },
    },
}


# =============================================================================
# MANUFACTURING PROFILE
# =============================================================================

MANUFACTURING = {
    "name": "Manufacturing",
    "slug": "manufacturing",
    "description": "Supply chain, procurement, quality management, and manufacturing contracts.",
    "contract_types": [
        {"code": "supply_agreement", "label": "Supply Agreement", "description": "Agreement for supply of goods/materials"},
        {"code": "quality_agreement", "label": "Quality Agreement", "description": "Quality standards and inspection terms"},
        {"code": "blanket_po", "label": "Blanket PO", "description": "Blanket Purchase Order for recurring supply"},
        {"code": "msa", "label": "MSA", "description": "Master Service/Supply Agreement"},
        {"code": "nda", "label": "NDA", "description": "Non-Disclosure Agreement"},
        {"code": "sow", "label": "SOW / Work Order", "description": "Statement of Work or Work Order"},
        {"code": "amendment", "label": "Amendment", "description": "Contract Amendment or Change Order"},
        {"code": "vendor_agreement", "label": "Vendor Agreement", "description": "General vendor/supplier terms"},
        {"code": "distribution", "label": "Distribution Agreement", "description": "Product distribution terms"},
        {"code": "tooling_agreement", "label": "Tooling Agreement", "description": "Tooling/mold ownership and maintenance"},
        {"code": "license", "label": "License", "description": "Technology or IP license"},
        {"code": "lease", "label": "Equipment Lease", "description": "Equipment or machinery lease"},
        {"code": "procurement_agreement", "label": "Procurement Agreement", "description": "Government or enterprise procurement contract (GCC/SCC)"},
        {"code": "manufacturing_supply", "label": "Manufacturing Supply Agreement", "description": "Agreement for manufacture and supply of custom goods"},
        {"code": "annual_maintenance", "label": "Annual Maintenance Contract", "description": "AMC for equipment or plant maintenance"},
        {"code": "rate_contract", "label": "Rate Contract", "description": "Pre-negotiated rate contract for recurring procurement"},
    ],
    "clause_types": [
        {"code": "quality_specs", "label": "Quality Specifications", "category": "quality", "risk_weight": 12},
        {"code": "inspection_rights", "label": "Inspection Rights", "category": "quality", "risk_weight": 8},
        {"code": "rejection_return", "label": "Rejection & Return", "category": "quality", "risk_weight": 10},
        {"code": "warranty", "label": "Product Warranty", "category": "quality", "risk_weight": 10},
        {"code": "delivery_terms", "label": "Delivery Terms (Incoterms)", "category": "logistics", "risk_weight": 8},
        {"code": "volume_commitment", "label": "Volume Commitment", "category": "commercial", "risk_weight": 10},
        {"code": "pricing_escalation", "label": "Price Escalation", "category": "commercial", "risk_weight": 12},
        {"code": "tooling_ownership", "label": "Tooling Ownership", "category": "ip", "risk_weight": 10},
        {"code": "engineering_change", "label": "Engineering Change (ECN)", "category": "operational", "risk_weight": 6},
        {"code": "safety_stock", "label": "Safety Stock / Buffer", "category": "logistics", "risk_weight": 6},
        {"code": "force_majeure", "label": "Force Majeure", "category": "general", "risk_weight": 8},
        {"code": "termination", "label": "Termination", "category": "general", "risk_weight": 10},
        {"code": "limitation_of_liability", "label": "Limitation of Liability", "category": "risk", "risk_weight": 15},
        {"code": "indemnification", "label": "Indemnification", "category": "risk", "risk_weight": 12},
        {"code": "confidentiality", "label": "Confidentiality", "category": "general", "risk_weight": 8},
        {"code": "ip", "label": "Intellectual Property", "category": "ip", "risk_weight": 10},
        {"code": "product_liability", "label": "Product Liability", "category": "risk", "risk_weight": 14},
        {"code": "recall", "label": "Recall Obligations", "category": "quality", "risk_weight": 12},
        {"code": "payment_terms", "label": "Payment Terms", "category": "commercial", "risk_weight": 5},
        {"code": "governing_law", "label": "Governing Law", "category": "general", "risk_weight": 3},
        {"code": "security_interest", "label": "Security Interest / UCC Lien", "category": "risk", "risk_weight": 14},
        {"code": "export_controls", "label": "Export Controls & Sanctions", "category": "regulatory", "risk_weight": 12},
        {"code": "govt_contracts", "label": "Government Contracts Restriction", "category": "regulatory", "risk_weight": 8},
        {"code": "unilateral_amendment", "label": "Unilateral Amendment Rights", "category": "risk", "risk_weight": 15},
        {"code": "assignment", "label": "Assignment & Transfer", "category": "general", "risk_weight": 6},
        {"code": "late_payment_penalty", "label": "Late Payment / Interest", "category": "commercial", "risk_weight": 8},
        {"code": "exclusive_remedy", "label": "Exclusive Remedy / Disclaimer", "category": "risk", "risk_weight": 12},
        {"code": "compliance_with_law", "label": "Compliance with Laws", "category": "regulatory", "risk_weight": 6},
    ],
    "risk_categories": [
        {"code": "supply_disruption", "label": "Supply Disruption", "severity": "critical", "weight": 20, "description": "Risk of supply chain interruption or single-source dependency"},
        {"code": "quality_nonconformance", "label": "Quality Non-Conformance", "severity": "high", "weight": 18, "description": "Risk of product quality failures or spec deviations"},
        {"code": "commodity_price", "label": "Commodity Price Exposure", "severity": "high", "weight": 15, "description": "Unhedged raw material price risk"},
        {"code": "tariff_exposure", "label": "Tariff / Trade Risk", "severity": "medium", "weight": 12, "description": "Exposure to tariffs, trade restrictions, or sanctions"},
        {"code": "product_liability", "label": "Product Liability", "severity": "critical", "weight": 20, "description": "Liability for defective products or recall costs"},
        {"code": "tooling_risk", "label": "Tooling / IP Risk", "severity": "medium", "weight": 10, "description": "Unclear tooling or mold ownership"},
        {"code": "volume_commitment", "label": "Volume Commitment Risk", "severity": "medium", "weight": 10, "description": "Take-or-pay or minimum volume obligations"},
        {"code": "delivery_failure", "label": "Delivery Failure", "severity": "high", "weight": 15, "description": "Risk of missed delivery windows impacting production"},
        {"code": "regulatory_compliance", "label": "Regulatory Compliance", "severity": "high", "weight": 14, "description": "Non-compliance with industry standards (ISO, ASTM, etc.)"},
        {"code": "single_source", "label": "Single Source Dependency", "severity": "high", "weight": 16, "description": "Sole supplier with no qualified alternative"},
        {"code": "export_sanctions", "label": "Export Control / Sanctions Risk", "severity": "high", "weight": 14, "description": "Exposure to export restrictions, denied parties, or trade sanctions"},
        {"code": "security_interest", "label": "Security Interest / Lien Exposure", "severity": "medium", "weight": 12, "description": "Supplier holds security interest or UCC lien on goods or inventory"},
        {"code": "unilateral_change", "label": "Unilateral Amendment Risk", "severity": "high", "weight": 16, "description": "Counterparty can modify terms without mutual agreement (e.g., via website posting)"},
        {"code": "govt_procurement", "label": "Government Procurement Risk", "severity": "medium", "weight": 10, "description": "Restrictions on resale to government entities or DFAR/FAR compliance requirements"},
    ],
    "sla_metrics": [
        {"code": "defect_ppm", "label": "Defect Rate (PPM)", "unit": "ppm", "direction": "lower_is_better", "default_target": 50},
        {"code": "on_time_delivery", "label": "On-Time Delivery", "unit": "percentage", "direction": "higher_is_better", "default_target": 98},
        {"code": "fill_rate", "label": "Fill Rate", "unit": "percentage", "direction": "higher_is_better", "default_target": 95},
        {"code": "lead_time", "label": "Lead Time", "unit": "days", "direction": "lower_is_better", "default_target": 14},
        {"code": "first_pass_yield", "label": "First Pass Yield", "unit": "percentage", "direction": "higher_is_better", "default_target": 99},
        {"code": "scrap_rate", "label": "Scrap Rate", "unit": "percentage", "direction": "lower_is_better", "default_target": 2},
        {"code": "corrective_action_time", "label": "Corrective Action Response", "unit": "days", "direction": "lower_is_better", "default_target": 5},
    ],
    "field_definitions": {
        "_default": [
            {"section": "Key Terms", "fields": [
                {"key": "effective_date", "label": "Effective Date", "type": "date"},
                {"key": "expiration_date", "label": "Expiration Date", "type": "date"},
                {"key": "contract_value", "label": "Annual Spend", "type": "currency"},
                {"key": "governing_law", "label": "Governing Law", "type": "text"},
                {"key": "auto_renewal", "label": "Auto-Renewal", "type": "boolean"},
                {"key": "incoterms", "label": "Incoterms", "type": "text"},
            ]},
            {"section": "Supplier", "fields": [
                {"key": "counterparty", "label": "Supplier", "type": "text"},
                {"key": "supplier_tier", "label": "Supplier Tier", "type": "text"},
                {"key": "supplier_location", "label": "Supplier Location", "type": "text"},
            ]},
            {"section": "Quality", "fields": [
                {"key": "quality_standard", "label": "Quality Standard", "type": "text"},
                {"key": "defect_ppm_target", "label": "Defect PPM Target", "type": "number"},
                {"key": "inspection_rights", "label": "Inspection Rights", "type": "boolean"},
                {"key": "ppap_required", "label": "PPAP Required", "type": "boolean"},
            ]},
            {"section": "Pricing", "fields": [
                {"key": "unit_price", "label": "Unit Price", "type": "currency"},
                {"key": "volume_tiers", "label": "Volume Pricing Tiers", "type": "text"},
                {"key": "price_escalation", "label": "Price Escalation Clause", "type": "text"},
                {"key": "minimum_order_qty", "label": "Minimum Order Quantity", "type": "number"},
            ]},
            {"section": "Logistics", "fields": [
                {"key": "delivery_schedule", "label": "Delivery Schedule", "type": "text"},
                {"key": "safety_stock_days", "label": "Safety Stock", "type": "number", "suffix": "days"},
                {"key": "lead_time_days", "label": "Lead Time", "type": "number", "suffix": "days"},
                {"key": "jit_required", "label": "JIT Delivery Required", "type": "boolean"},
            ]},
        ],
    },
    "extraction_hints": {
        "metadata": "Extract: parties (identify supplier/manufacturer vs buyer/customer), effective/expiry dates, initial term and renewal terms (auto-renewal period, non-renewal notice days), total value or annual spend, Incoterms (FOB, DDP, CIF, etc.), volume commitments, governing law and jurisdiction. For procurement contracts, identify tender/bid references, purchase order structure, and pricing basis (fixed, market-indexed, gold/commodity-linked).",
        "clauses": "Focus on: quality specifications (ISO, ASTM standards), inspection and audit rights (inspection periods, acceptance/rejection windows), rejection/return procedures, warranty terms (duration, scope, limitations, exclusive remedy), delivery terms (Incoterms, late delivery thresholds, cancellation rights), pricing and escalation (commodity-linked pricing, gold market references), tooling ownership, engineering change notice procedures, force majeure (trigger thresholds, termination rights), product liability and recall, security interest/UCC liens on goods or inventory, export controls and sanctions compliance, government contracts restrictions (DFAR/FAR), unilateral amendment rights (especially amendments via website posting or unilateral notice), assignment restrictions, late payment penalties and interest rates, exclusive remedy and warranty disclaimer clauses.",
        "risks": "Evaluate: single-source supplier dependency, commodity price exposure without hedging (gold, steel, resin price volatility), quality non-conformance history, tariff/trade risk for cross-border supply, product liability and recall cost allocation, volume commitment (take-or-pay), delivery failure impact on production schedule, security interest or UCC lien exposure (supplier holding first-priority lien on goods), export control violations, unilateral amendment rights that allow counterparty to change terms without mutual consent, government procurement compliance (DFAR, FAR, anti-corruption).",
        "slas": "Look for: defect rate targets (PPM), on-time delivery percentage, fill rate, lead time commitments, first pass yield requirements, scrap rate limits, corrective action response time, inspection period windows (days to inspect/reject), warranty period duration, late delivery thresholds (days before cancellation right triggers), cure period durations.",
        "obligations": "Extract: quality audit obligations (annual, surprise), certification maintenance (ISO 9001, IATF 16949), PPAP submission requirements, corrective action timelines, safety stock maintenance, production capacity reservations, engineering change notice timelines, inspection period deadlines (e.g., 5 days to report nonconforming goods), defect notification deadlines, goods return/destruction certification deadlines, breach cure periods (e.g., 30 days to cure, 14 days for payment default), non-renewal notice periods (e.g., 90 days), indemnification claim response deadlines, confidential information return/destruction upon termination, export compliance certifications.",
    },
    "ui_config": {
        "table_columns": [
            {"key": "filename", "label": "Contract Name", "width": 260},
            {"key": "contract_type", "label": "Type", "width": 120},
            {"key": "counterparty", "label": "Supplier", "width": 180},
            {"key": "contract_value", "label": "Annual Spend", "format": "currency", "width": 120},
            {"key": "risk_level", "label": "Risk", "width": 80},
            {"key": "expiration_date", "label": "Expiry", "format": "date", "width": 100},
        ],
        "dashboard_widgets": [
            {"key": "total_contracts", "label": "Total Contracts", "color": "primary", "icon": "document"},
            {"key": "at_risk", "label": "Supply Risk", "color": "danger", "icon": "warning"},
            {"key": "compliance_rate", "label": "Quality Score", "color": "success", "icon": "check", "format": "percentage"},
            {"key": "total_value", "label": "Annual Spend", "color": "blue", "icon": "currency", "format": "currency"},
            {"key": "obligation_rate", "label": "OTD %", "color": "warning", "icon": "truck", "format": "percentage"},
            {"key": "sla_rate", "label": "Defect PPM", "color": "success", "icon": "shield", "format": "number"},
        ],
        "detail_tabs": [
            {"id": "overview", "label": "Overview", "icon": "document"},
            {"id": "review", "label": "Review", "icon": "eye"},
            {"id": "quality", "label": "Quality", "icon": "shield"},
            {"id": "supply_chain", "label": "Supply Chain", "icon": "truck"},
            {"id": "related", "label": "Related Docs", "icon": "link"},
            {"id": "documents", "label": "Documents", "icon": "folder"},
        ],
        "filters": ["contract_type", "risk_level", "status", "business_unit", "supplier_tier"],
        "labels": {
            "counterparty": "Supplier",
            "contract_value": "Annual Spend",
            "portfolio": "Procurement Dashboard",
        },
    },
}


# =============================================================================
# PHARMA / LIFE SCIENCES PROFILE
# =============================================================================

PHARMA = {
    "name": "Pharma / Life Sciences",
    "slug": "pharma",
    "description": "Pharmaceutical, biotech, medical devices, and clinical research contracts.",
    "contract_types": [
        {"code": "csa", "label": "Clinical Study Agreement", "description": "Agreement governing clinical trial conduct"},
        {"code": "quality_agreement", "label": "Quality Agreement", "description": "GMP/GDP quality terms between parties"},
        {"code": "cda", "label": "CDA", "description": "Confidential Disclosure Agreement"},
        {"code": "supply_agreement", "label": "Drug Supply Agreement", "description": "API or finished product supply"},
        {"code": "msa", "label": "MSA", "description": "Master Service Agreement"},
        {"code": "sow", "label": "SOW / Work Order", "description": "Statement of Work for services"},
        {"code": "cmo_agreement", "label": "CMO Agreement", "description": "Contract Manufacturing Organization agreement"},
        {"code": "cro_agreement", "label": "CRO Agreement", "description": "Contract Research Organization agreement"},
        {"code": "license", "label": "License Agreement", "description": "IP/patent license or co-development"},
        {"code": "distribution", "label": "Distribution Agreement", "description": "Drug distribution and marketing"},
        {"code": "pharmacovigilance", "label": "PV Agreement", "description": "Pharmacovigilance / safety data exchange"},
        {"code": "amendment", "label": "Amendment", "description": "Contract amendment or protocol change"},
        {"code": "nda", "label": "NDA", "description": "Non-Disclosure Agreement"},
    ],
    "clause_types": [
        {"code": "gmp_compliance", "label": "GMP Compliance", "category": "regulatory", "risk_weight": 15},
        {"code": "pharmacovigilance", "label": "Pharmacovigilance", "category": "regulatory", "risk_weight": 14},
        {"code": "regulatory_submission", "label": "Regulatory Submissions", "category": "regulatory", "risk_weight": 12},
        {"code": "data_integrity", "label": "Data Integrity", "category": "regulatory", "risk_weight": 13},
        {"code": "audit_rights", "label": "Audit & Inspection Rights", "category": "quality", "risk_weight": 10},
        {"code": "deviation_handling", "label": "Deviation Handling", "category": "quality", "risk_weight": 10},
        {"code": "recall", "label": "Product Recall", "category": "quality", "risk_weight": 14},
        {"code": "batch_release", "label": "Batch Release / QP", "category": "quality", "risk_weight": 10},
        {"code": "stability_testing", "label": "Stability Testing", "category": "quality", "risk_weight": 8},
        {"code": "tech_transfer", "label": "Technology Transfer", "category": "ip", "risk_weight": 12},
        {"code": "ip", "label": "Intellectual Property", "category": "ip", "risk_weight": 12},
        {"code": "confidentiality", "label": "Confidentiality", "category": "general", "risk_weight": 10},
        {"code": "termination", "label": "Termination", "category": "general", "risk_weight": 10},
        {"code": "limitation_of_liability", "label": "Limitation of Liability", "category": "risk", "risk_weight": 15},
        {"code": "indemnification", "label": "Indemnification", "category": "risk", "risk_weight": 12},
        {"code": "insurance", "label": "Insurance Requirements", "category": "risk", "risk_weight": 8},
        {"code": "governing_law", "label": "Governing Law", "category": "general", "risk_weight": 3},
        {"code": "force_majeure", "label": "Force Majeure", "category": "general", "risk_weight": 5},
        {"code": "payment_terms", "label": "Payment Terms", "category": "commercial", "risk_weight": 5},
    ],
    "risk_categories": [
        {"code": "gmp_noncompliance", "label": "GMP Non-Compliance", "severity": "critical", "weight": 25, "description": "Failure to maintain GMP standards; FDA warning letter risk"},
        {"code": "data_integrity_breach", "label": "Data Integrity Breach", "severity": "critical", "weight": 22, "description": "ALCOA+ violations; regulatory submission risk"},
        {"code": "pharmacovigilance_gap", "label": "Pharmacovigilance Gap", "severity": "critical", "weight": 20, "description": "Inadequate safety reporting or adverse event handling"},
        {"code": "supply_disruption", "label": "Supply Disruption", "severity": "high", "weight": 18, "description": "Risk to drug supply continuity"},
        {"code": "regulatory_delay", "label": "Regulatory Delay", "severity": "high", "weight": 15, "description": "Risk of delayed regulatory approval or filing"},
        {"code": "product_recall", "label": "Product Recall Risk", "severity": "critical", "weight": 20, "description": "Recall cost allocation and product liability"},
        {"code": "ip_ownership", "label": "IP Ownership Dispute", "severity": "high", "weight": 14, "description": "Unclear patent/IP ownership from co-development"},
        {"code": "audit_limitation", "label": "Audit Right Limitation", "severity": "medium", "weight": 10, "description": "Restricted audit or inspection access"},
        {"code": "tech_transfer_risk", "label": "Technology Transfer Risk", "severity": "medium", "weight": 12, "description": "Risk of incomplete or failed tech transfer"},
        {"code": "insurance_gap", "label": "Insurance Coverage Gap", "severity": "medium", "weight": 8, "description": "Inadequate clinical trial or product liability insurance"},
    ],
    "sla_metrics": [
        {"code": "batch_release_time", "label": "Batch Release Time", "unit": "days", "direction": "lower_is_better", "default_target": 14},
        {"code": "deviation_closure", "label": "Deviation Closure Time", "unit": "days", "direction": "lower_is_better", "default_target": 30},
        {"code": "stability_completion", "label": "Stability Study Completion", "unit": "percentage", "direction": "higher_is_better", "default_target": 100},
        {"code": "audit_response", "label": "Audit Response Time", "unit": "days", "direction": "lower_is_better", "default_target": 5},
        {"code": "capa_effectiveness", "label": "CAPA Effectiveness", "unit": "percentage", "direction": "higher_is_better", "default_target": 95},
        {"code": "on_time_delivery", "label": "On-Time Delivery", "unit": "percentage", "direction": "higher_is_better", "default_target": 98},
        {"code": "yield_rate", "label": "Batch Yield Rate", "unit": "percentage", "direction": "higher_is_better", "default_target": 95},
    ],
    "field_definitions": {
        "_default": [
            {"section": "Key Terms", "fields": [
                {"key": "effective_date", "label": "Effective Date", "type": "date"},
                {"key": "expiration_date", "label": "Expiration Date", "type": "date"},
                {"key": "contract_value", "label": "Study Budget / Value", "type": "currency"},
                {"key": "governing_law", "label": "Governing Law", "type": "text"},
                {"key": "therapeutic_area", "label": "Therapeutic Area", "type": "text"},
            ]},
            {"section": "Parties", "fields": [
                {"key": "counterparty", "label": "Partner / CRO / CMO", "type": "text"},
                {"key": "sponsor", "label": "Sponsor", "type": "text"},
                {"key": "qualified_person", "label": "Qualified Person (QP)", "type": "text"},
            ]},
            {"section": "Regulatory", "fields": [
                {"key": "regulatory_authority", "label": "Regulatory Authority", "type": "text"},
                {"key": "gmp_standard", "label": "GMP Standard", "type": "text"},
                {"key": "market_authorization", "label": "Market Authorization", "type": "text"},
                {"key": "clinical_phase", "label": "Clinical Phase", "type": "text"},
            ]},
            {"section": "Quality", "fields": [
                {"key": "quality_agreement_ref", "label": "Quality Agreement Reference", "type": "text"},
                {"key": "deviation_process", "label": "Deviation Process", "type": "text"},
                {"key": "change_control", "label": "Change Control Process", "type": "text"},
                {"key": "annual_review", "label": "Annual Product Review", "type": "boolean"},
            ]},
            {"section": "Safety", "fields": [
                {"key": "pv_agreement_ref", "label": "PV Agreement Reference", "type": "text"},
                {"key": "safety_reporting_timeline", "label": "Safety Reporting Timeline", "type": "text"},
                {"key": "susar_reporting", "label": "SUSAR Reporting", "type": "text"},
            ]},
        ],
    },
    "extraction_hints": {
        "metadata": "Extract: parties (identify sponsor, CRO, CMO, site), effective/expiry dates, study budget or contract value, therapeutic area, clinical phase (I/II/III/IV), regulatory authority (FDA/EMA/MHRA), governing law.",
        "clauses": "Focus on: GMP/GCP/GLP compliance requirements, pharmacovigilance and safety reporting, regulatory submission responsibilities, data integrity (ALCOA+), audit and inspection rights, deviation and CAPA handling, product recall obligations, batch release and QP responsibilities, technology transfer, IP ownership from co-development, insurance requirements (clinical trial insurance, product liability).",
        "risks": "Evaluate: GMP non-compliance risk (warning letters, consent decrees), data integrity breaches (21 CFR Part 11, Annex 11), pharmacovigilance gaps (SUSAR/CIOMS reporting), supply disruption for critical APIs, regulatory delay risk, product recall cost allocation, IP ownership disputes from co-development, audit right limitations, technology transfer completeness.",
        "slas": "Look for: batch release time targets, deviation closure timelines, stability study completion, CAPA effectiveness rates, audit response times, on-time delivery, batch yield rates.",
        "obligations": "Extract: GMP audit schedules (annual, for-cause), regulatory filing deadlines, safety report timelines (7-day, 15-day), annual product quality review, change control notification, stability study commitments, training and qualification requirements, batch record retention periods.",
    },
    "ui_config": {
        "table_columns": [
            {"key": "filename", "label": "Contract Name", "width": 260},
            {"key": "contract_type", "label": "Type", "width": 120},
            {"key": "counterparty", "label": "Partner", "width": 180},
            {"key": "contract_value", "label": "Budget", "format": "currency", "width": 120},
            {"key": "risk_level", "label": "Risk", "width": 80},
            {"key": "expiration_date", "label": "Expiry", "format": "date", "width": 100},
        ],
        "dashboard_widgets": [
            {"key": "total_contracts", "label": "Total Contracts", "color": "primary", "icon": "document"},
            {"key": "at_risk", "label": "Regulatory Gaps", "color": "danger", "icon": "warning"},
            {"key": "compliance_rate", "label": "GMP Compliance", "color": "success", "icon": "check", "format": "percentage"},
            {"key": "total_value", "label": "Study Budget", "color": "blue", "icon": "currency", "format": "currency"},
            {"key": "obligation_rate", "label": "Audit Status", "color": "warning", "icon": "clipboard", "format": "percentage"},
            {"key": "sla_rate", "label": "Deviation Backlog", "color": "success", "icon": "chart", "format": "number"},
        ],
        "detail_tabs": [
            {"id": "overview", "label": "Overview", "icon": "document"},
            {"id": "review", "label": "Review", "icon": "eye"},
            {"id": "regulatory", "label": "Regulatory", "icon": "shield"},
            {"id": "quality", "label": "Quality", "icon": "check"},
            {"id": "related", "label": "Related Docs", "icon": "link"},
            {"id": "documents", "label": "Documents", "icon": "folder"},
        ],
        "filters": ["contract_type", "risk_level", "status", "business_unit", "therapeutic_area"],
        "labels": {
            "counterparty": "Partner",
            "contract_value": "Study Budget",
            "portfolio": "Regulatory Dashboard",
        },
    },
}


# =============================================================================
# SEEDING LOGIC
# =============================================================================

PROFILES = [IT_SERVICES, MANUFACTURING, PHARMA]


async def seed_industry_profiles():
    """Seed industry profiles."""
    print("=" * 60)
    print("Seeding Industry Profiles")
    print("=" * 60)

    async with async_session_maker() as db:
        for profile_data in PROFILES:
            slug = profile_data["slug"]
            existing = await db.execute(
                select(IndustryProfile).where(IndustryProfile.slug == slug)
            )
            profile = existing.scalar_one_or_none()

            if profile:
                # Update existing profile with latest data
                profile.name = profile_data["name"]
                profile.description = profile_data["description"]
                profile.contract_types = profile_data["contract_types"]
                profile.clause_types = profile_data["clause_types"]
                profile.risk_categories = profile_data["risk_categories"]
                profile.sla_metrics = profile_data["sla_metrics"]
                profile.field_definitions = profile_data["field_definitions"]
                profile.extraction_hints = profile_data["extraction_hints"]
                profile.ui_config = profile_data["ui_config"]
                print(f"  ~ Updated: {profile_data['name']}")
            else:
                profile = IndustryProfile(
                    name=profile_data["name"],
                    slug=slug,
                    description=profile_data["description"],
                    contract_types=profile_data["contract_types"],
                    clause_types=profile_data["clause_types"],
                    risk_categories=profile_data["risk_categories"],
                    sla_metrics=profile_data["sla_metrics"],
                    field_definitions=profile_data["field_definitions"],
                    extraction_hints=profile_data["extraction_hints"],
                    ui_config=profile_data["ui_config"],
                )
                db.add(profile)
                print(f"  + Created: {profile_data['name']}")

        await db.commit()

    print("\n" + "=" * 60)
    print("Industry profiles seeded!")
    print("=" * 60)


async def assign_default_profiles():
    """Assign IT Services profile to all tenants that don't have a profile."""
    print("\n" + "=" * 60)
    print("Assigning Default Profiles to Tenants")
    print("=" * 60)

    from app.models import Tenant

    async with async_session_maker() as db:
        # Get IT Services profile
        result = await db.execute(
            select(IndustryProfile).where(IndustryProfile.slug == "it-services")
        )
        it_profile = result.scalar_one_or_none()

        if not it_profile:
            print("  ! IT Services profile not found")
            return

        # Get tenants without a profile
        tenants_result = await db.execute(
            select(Tenant).where(
                Tenant.is_active == True,
                Tenant.industry_profile_id == None,
            )
        )
        tenants = tenants_result.scalars().all()

        for tenant in tenants:
            tenant.industry_profile_id = it_profile.id
            print(f"  + {tenant.name} -> IT Services")

        await db.commit()

    print("\n" + "=" * 60)
    print("Default profiles assigned!")
    print("=" * 60)


async def print_summary():
    """Print profile summary."""
    print("\n" + "=" * 60)
    print("INDUSTRY PROFILE SUMMARY")
    print("=" * 60)

    async with async_session_maker() as db:
        result = await db.execute(select(IndustryProfile).where(IndustryProfile.is_active == True))
        profiles = result.scalars().all()

        for p in profiles:
            print(f"\n{p.name} ({p.slug}):")
            print(f"  Contract types: {len(p.contract_types)}")
            print(f"  Clause types:   {len(p.clause_types)}")
            print(f"  Risk categories:{len(p.risk_categories)}")
            print(f"  SLA metrics:    {len(p.sla_metrics)}")
            print(f"  Extraction hints: {len(p.extraction_hints)} agents")

    print("\n" + "=" * 60)


async def main():
    await seed_industry_profiles()
    await assign_default_profiles()
    await print_summary()


if __name__ == "__main__":
    asyncio.run(main())
