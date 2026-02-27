"""Industry and Compliance enums for the Industry-Aware Compliance Module.

This module provides enums for industry classification, compliance document types,
and compliance gap tracking.
"""

import enum


class Industry(str, enum.Enum):
    """Industry classification for contracts."""

    PHARMACEUTICAL = "pharmaceutical"
    HEALTHCARE = "healthcare"
    CHEMICAL = "chemical"
    MANUFACTURING = "manufacturing"
    TECHNOLOGY = "technology"
    FINANCIAL_SERVICES = "financial_services"
    ENERGY = "energy"
    AEROSPACE_DEFENSE = "aerospace_defense"
    FOOD_BEVERAGE = "food_beverage"
    AUTOMOTIVE = "automotive"
    TELECOMMUNICATIONS = "telecommunications"
    RETAIL = "retail"
    CONSTRUCTION = "construction"
    PROFESSIONAL_SERVICES = "professional_services"
    OTHER = "other"


class ComplianceDocumentType(str, enum.Enum):
    """Types of compliance documents that may be required."""

    # Pharmaceutical/Healthcare
    QUALITY_AGREEMENT = "quality_agreement"
    PHARMACOVIGILANCE_AGREEMENT = "pharmacovigilance_agreement"
    TECHNICAL_AGREEMENT = "technical_agreement"
    SAFETY_DATA_EXCHANGE_AGREEMENT = "safety_data_exchange_agreement"

    # Healthcare/Data Privacy
    BAA = "baa"  # Business Associate Agreement (HIPAA)
    DPA = "dpa"  # Data Processing Agreement (GDPR)
    SCC = "scc"  # Standard Contractual Clauses

    # Manufacturing/Supply Chain
    PRODUCT_SPECIFICATIONS = "product_specifications"
    QUALITY_MANAGEMENT_PLAN = "quality_management_plan"
    SUPPLIER_QUALITY_AGREEMENT = "supplier_quality_agreement"

    # Chemical/Safety
    SAFETY_DATA_SHEET = "safety_data_sheet"
    ENVIRONMENTAL_COMPLIANCE_PLAN = "environmental_compliance_plan"

    # Technology
    SECURITY_ADDENDUM = "security_addendum"
    SOC2_REPORT = "soc2_report"
    PENETRATION_TEST_REPORT = "penetration_test_report"

    # Financial Services
    OUTSOURCING_AGREEMENT = "outsourcing_agreement"
    BCDR_PLAN = "bcdr_plan"  # Business Continuity/Disaster Recovery

    # General
    INSURANCE_CERTIFICATE = "insurance_certificate"
    AUDIT_REPORT = "audit_report"
    COMPLIANCE_CERTIFICATION = "compliance_certification"


class ComplianceGapSeverity(str, enum.Enum):
    """Severity level of a compliance gap."""

    CRITICAL = "critical"  # Immediate regulatory risk, may halt operations
    HIGH = "high"  # Significant compliance risk, urgent attention needed
    MEDIUM = "medium"  # Moderate risk, should be addressed
    LOW = "low"  # Minor gap, can be addressed in normal course


class ComplianceGapStatus(str, enum.Enum):
    """Status of a compliance gap."""

    OPEN = "open"  # Gap identified, not yet addressed
    IN_PROGRESS = "in_progress"  # Being worked on
    PENDING_REVIEW = "pending_review"  # Resolution submitted, awaiting review
    RESOLVED = "resolved"  # Gap addressed with appropriate documentation
    WAIVED = "waived"  # Requirement waived (with documentation)
    NOT_APPLICABLE = "not_applicable"  # Gap determined to not apply


# Constants for regulated industries that require special extraction
REGULATED_INDUSTRIES = frozenset([
    Industry.PHARMACEUTICAL,
    Industry.HEALTHCARE,
    Industry.CHEMICAL,
    Industry.FINANCIAL_SERVICES,
    Industry.AEROSPACE_DEFENSE,
    Industry.FOOD_BEVERAGE,
])
