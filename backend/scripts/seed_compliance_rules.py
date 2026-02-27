#!/usr/bin/env python3
"""
Seed script to populate the database with default compliance rules.
Run with: python -m scripts.seed_compliance_rules

These rules define required compliance documents for each industry and contract type.
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.tenant import Tenant
from app.models.contract import ContractType
from app.models.industry import (
    Industry,
    ComplianceDocumentType,
    ComplianceGapSeverity,
)
from app.models.compliance_rule import IndustryComplianceRule


# Default compliance rules organized by industry
DEFAULT_COMPLIANCE_RULES = [
    # ===== PHARMACEUTICAL INDUSTRY =====
    {
        "industry": Industry.PHARMACEUTICAL,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.QUALITY_AGREEMENT,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "21 CFR Part 211 (GMP)",
        "rule_name": "Quality Agreement Required",
        "rule_description": (
            "FDA requires Quality Agreements for all pharmaceutical manufacturing "
            "relationships. This document defines quality responsibilities, "
            "change control procedures, and right to audit."
        ),
    },
    {
        "industry": Industry.PHARMACEUTICAL,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.PHARMACOVIGILANCE_AGREEMENT,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "21 CFR Part 312 / ICH E2A",
        "rule_name": "Pharmacovigilance Agreement Required",
        "rule_description": (
            "Safety Data Exchange Agreement (SDEA) required for pharmaceutical "
            "partnerships to define adverse event reporting responsibilities "
            "and timelines per FDA/ICH guidelines."
        ),
    },
    {
        "industry": Industry.PHARMACEUTICAL,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.QUALITY_AGREEMENT,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "21 CFR Part 211.84",
        "rule_name": "Supplier Quality Agreement",
        "rule_description": (
            "Quality Agreement required for all pharmaceutical suppliers "
            "to ensure GMP compliance throughout the supply chain."
        ),
    },
    {
        "industry": Industry.PHARMACEUTICAL,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.PRODUCT_SPECIFICATIONS,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "21 CFR Part 211.22",
        "rule_name": "Product Specifications Required",
        "rule_description": (
            "Material specifications required for all raw materials "
            "and API suppliers per GMP requirements."
        ),
    },

    # ===== HEALTHCARE INDUSTRY =====
    {
        "industry": Industry.HEALTHCARE,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.BAA,
        "is_required": True,
        "condition_description": "Required when PHI is involved",
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "HIPAA 45 CFR 164.502(e)",
        "rule_name": "Business Associate Agreement (BAA)",
        "rule_description": (
            "HIPAA requires a Business Associate Agreement with any third party "
            "that creates, receives, maintains, or transmits Protected Health "
            "Information (PHI) on behalf of a Covered Entity."
        ),
    },
    {
        "industry": Industry.HEALTHCARE,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.BAA,
        "is_required": True,
        "condition_description": "Required when PHI is involved",
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "HIPAA 45 CFR 164.504(e)",
        "rule_name": "Vendor BAA Required",
        "rule_description": (
            "Business Associate Agreement required for all vendors "
            "with access to PHI or healthcare data systems."
        ),
    },
    {
        "industry": Industry.HEALTHCARE,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.SECURITY_ADDENDUM,
        "is_required": False,
        "condition_description": "Recommended for all healthcare IT services",
        "severity_if_missing": ComplianceGapSeverity.MEDIUM,
        "regulatory_reference": "HIPAA Security Rule",
        "rule_name": "Security Addendum Recommended",
        "rule_description": (
            "Security addendum documenting technical safeguards, "
            "access controls, and incident response procedures."
        ),
    },

    # ===== TECHNOLOGY INDUSTRY =====
    {
        "industry": Industry.TECHNOLOGY,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.DPA,
        "is_required": True,
        "condition_description": "Required when processing personal data",
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "GDPR Article 28",
        "rule_name": "Data Processing Agreement (GDPR)",
        "rule_description": (
            "GDPR requires a Data Processing Agreement when a controller "
            "engages a processor to process personal data on their behalf."
        ),
    },
    {
        "industry": Industry.TECHNOLOGY,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.DPA,
        "is_required": True,
        "condition_description": "Required for SaaS/cloud vendors processing personal data",
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "GDPR Article 28",
        "rule_name": "Vendor DPA Required",
        "rule_description": (
            "Data Processing Agreement required for all SaaS/cloud vendors "
            "that process personal data as part of their services."
        ),
    },
    {
        "industry": Industry.TECHNOLOGY,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.SECURITY_ADDENDUM,
        "is_required": False,
        "severity_if_missing": ComplianceGapSeverity.MEDIUM,
        "regulatory_reference": "SOC 2 / ISO 27001",
        "rule_name": "Security Addendum Recommended",
        "rule_description": (
            "Security addendum recommended for technology services "
            "to document security controls and certifications."
        ),
    },
    {
        "industry": Industry.TECHNOLOGY,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.SOC2_REPORT,
        "is_required": False,
        "severity_if_missing": ComplianceGapSeverity.LOW,
        "regulatory_reference": "AICPA SOC 2",
        "rule_name": "SOC 2 Report Recommended",
        "rule_description": (
            "SOC 2 Type II report recommended to verify security, "
            "availability, and processing integrity controls."
        ),
    },

    # ===== CHEMICAL INDUSTRY =====
    {
        "industry": Industry.CHEMICAL,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.SAFETY_DATA_SHEET,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "OSHA 29 CFR 1910.1200",
        "rule_name": "Safety Data Sheet (SDS) Required",
        "rule_description": (
            "OSHA Hazard Communication Standard requires Safety Data Sheets "
            "for all hazardous chemicals in the workplace."
        ),
    },
    {
        "industry": Industry.CHEMICAL,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.ENVIRONMENTAL_COMPLIANCE_PLAN,
        "is_required": False,
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "EPA RCRA / TSCA",
        "rule_name": "Environmental Compliance Plan",
        "rule_description": (
            "Environmental compliance documentation recommended for "
            "chemical handling, storage, and disposal procedures."
        ),
    },
    {
        "industry": Industry.CHEMICAL,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.PRODUCT_SPECIFICATIONS,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "REACH / TSCA",
        "rule_name": "Chemical Specifications Required",
        "rule_description": (
            "Product specifications including CAS numbers, purity levels, "
            "and composition required for all chemical suppliers."
        ),
    },

    # ===== MANUFACTURING INDUSTRY =====
    {
        "industry": Industry.MANUFACTURING,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.SUPPLIER_QUALITY_AGREEMENT,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "ISO 9001",
        "rule_name": "Supplier Quality Agreement",
        "rule_description": (
            "Quality agreement required for manufacturing suppliers "
            "to define quality standards, inspection procedures, "
            "and non-conformance handling."
        ),
    },
    {
        "industry": Industry.MANUFACTURING,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.PRODUCT_SPECIFICATIONS,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "ISO 9001 / Customer Requirements",
        "rule_name": "Product Specifications Required",
        "rule_description": (
            "Technical specifications, drawings, and tolerances "
            "required for all manufacturing components."
        ),
    },
    {
        "industry": Industry.MANUFACTURING,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.QUALITY_MANAGEMENT_PLAN,
        "is_required": False,
        "severity_if_missing": ComplianceGapSeverity.MEDIUM,
        "regulatory_reference": "ISO 9001",
        "rule_name": "Quality Management Plan",
        "rule_description": (
            "Quality management plan recommended for manufacturing "
            "relationships to document quality processes and KPIs."
        ),
    },

    # ===== FINANCIAL SERVICES INDUSTRY =====
    {
        "industry": Industry.FINANCIAL_SERVICES,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.OUTSOURCING_AGREEMENT,
        "is_required": True,
        "condition_description": "Required for critical/significant outsourcing",
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "OCC Bulletin 2013-29 / FFIEC",
        "rule_name": "Outsourcing Agreement Required",
        "rule_description": (
            "Regulatory guidance requires formal outsourcing agreements "
            "for critical financial service functions with defined SLAs, "
            "audit rights, and business continuity provisions."
        ),
    },
    {
        "industry": Industry.FINANCIAL_SERVICES,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.BCDR_PLAN,
        "is_required": False,
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "FFIEC BCP Handbook",
        "rule_name": "BCDR Documentation",
        "rule_description": (
            "Business Continuity and Disaster Recovery plan documentation "
            "recommended for critical technology and service providers."
        ),
    },
    {
        "industry": Industry.FINANCIAL_SERVICES,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.SECURITY_ADDENDUM,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.HIGH,
        "regulatory_reference": "GLBA / NY DFS Cybersecurity",
        "rule_name": "Security Addendum Required",
        "rule_description": (
            "Security addendum required to document cybersecurity controls "
            "and compliance with financial services security regulations."
        ),
    },

    # ===== FOOD & BEVERAGE INDUSTRY =====
    {
        "industry": Industry.FOOD_BEVERAGE,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.QUALITY_AGREEMENT,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "FDA FSMA / GFSI",
        "rule_name": "Food Safety Quality Agreement",
        "rule_description": (
            "Quality agreement required for food ingredient and co-manufacturing "
            "suppliers per FSMA and GFSI (SQF, BRC, FSSC 22000) requirements."
        ),
    },
    {
        "industry": Industry.FOOD_BEVERAGE,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.PRODUCT_SPECIFICATIONS,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "FDA FSMA 21 CFR 117",
        "rule_name": "Ingredient Specifications Required",
        "rule_description": (
            "Product specifications including allergen declarations, "
            "nutritional data, and certificates of analysis required."
        ),
    },

    # ===== AEROSPACE & DEFENSE INDUSTRY =====
    {
        "industry": Industry.AEROSPACE_DEFENSE,
        "primary_contract_type": ContractType.VENDOR_AGREEMENT,
        "required_document_type": ComplianceDocumentType.QUALITY_AGREEMENT,
        "is_required": True,
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "AS9100 / NADCAP",
        "rule_name": "Aerospace Quality Agreement",
        "rule_description": (
            "Quality agreement required for aerospace suppliers "
            "meeting AS9100 and NADCAP requirements for flight-critical components."
        ),
    },
    {
        "industry": Industry.AEROSPACE_DEFENSE,
        "primary_contract_type": ContractType.MSA,
        "required_document_type": ComplianceDocumentType.SECURITY_ADDENDUM,
        "is_required": True,
        "condition_description": "Required for defense/classified work",
        "severity_if_missing": ComplianceGapSeverity.CRITICAL,
        "regulatory_reference": "DFARS / NIST SP 800-171",
        "rule_name": "Defense Security Addendum",
        "rule_description": (
            "Security addendum required for defense contracts "
            "documenting CUI handling and DFARS compliance."
        ),
    },
]


async def seed_compliance_rules(tenant_id: UUID | None = None):
    """Seed default compliance rules to the database."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Get tenant(s) to seed rules for
        if tenant_id:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenants = [result.scalar_one()]
        else:
            # Get all tenants
            result = await session.execute(select(Tenant))
            tenants = result.scalars().all()

        if not tenants:
            print("No tenants found. Please create a tenant first.")
            return

        for tenant in tenants:
            print(f"\nSeeding compliance rules for tenant: {tenant.name}")

            # Check existing rules for this tenant
            existing_result = await session.execute(
                select(IndustryComplianceRule)
                .where(IndustryComplianceRule.tenant_id == tenant.id)
            )
            existing_rules = existing_result.scalars().all()

            # Create a set of existing rule keys for deduplication
            existing_keys = {
                (r.industry, r.primary_contract_type, r.required_document_type)
                for r in existing_rules
            }

            created_count = 0
            skipped_count = 0

            for rule_data in DEFAULT_COMPLIANCE_RULES:
                key = (
                    rule_data["industry"],
                    rule_data["primary_contract_type"],
                    rule_data["required_document_type"],
                )

                if key in existing_keys:
                    skipped_count += 1
                    continue

                rule = IndustryComplianceRule(
                    tenant_id=tenant.id,
                    industry=rule_data["industry"],
                    primary_contract_type=rule_data["primary_contract_type"],
                    required_document_type=rule_data["required_document_type"],
                    is_required=rule_data.get("is_required", True),
                    condition_description=rule_data.get("condition_description"),
                    severity_if_missing=rule_data.get(
                        "severity_if_missing", ComplianceGapSeverity.MEDIUM
                    ),
                    regulatory_reference=rule_data.get("regulatory_reference"),
                    rule_name=rule_data["rule_name"],
                    rule_description=rule_data.get("rule_description"),
                    is_active=True,
                )
                session.add(rule)
                created_count += 1

            await session.commit()
            print(f"  Created: {created_count} rules")
            print(f"  Skipped (already exists): {skipped_count} rules")

    print("\nCompliance rules seeding completed!")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed compliance rules")
    parser.add_argument(
        "--tenant-id",
        type=str,
        help="Specific tenant ID to seed rules for (seeds all tenants if not specified)",
    )
    args = parser.parse_args()

    tenant_id = UUID(args.tenant_id) if args.tenant_id else None
    await seed_compliance_rules(tenant_id)


if __name__ == "__main__":
    asyncio.run(main())
