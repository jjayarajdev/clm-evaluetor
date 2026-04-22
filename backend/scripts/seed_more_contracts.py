"""Seed additional contracts into tenants that have too few, with BU assignment."""

import asyncio
import sys
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import Tenant, User, Contract
from app.models.user import Role
from app.models.contract import ContractStatus, ContractType, RiskLevel
from app.models.business_unit import BusinessUnit

# Minimum contracts per tenant for a good demo
MIN_CONTRACTS = 20

# Contract templates — realistic variety
CONTRACT_TEMPLATES = [
    # Procurement BU contracts
    {"filename": "Vendor-Agreement-CloudInfra-2025.pdf", "contract_type": "vendor_agreement", "counterparty": "CloudInfra Solutions", "value": Decimal("890000"), "risk": "medium", "risk_score": 45, "bu_code": "PROC"},
    {"filename": "MSA-DataAnalytics-Platform.pdf", "contract_type": "msa", "counterparty": "DataAnalytics Corp", "value": Decimal("1250000"), "risk": "high", "risk_score": 72, "bu_code": "PROC"},
    {"filename": "Vendor-Agreement-CyberSecurity.pdf", "contract_type": "vendor_agreement", "counterparty": "CyberShield Inc", "value": Decimal("340000"), "risk": "low", "risk_score": 18, "bu_code": "PROC"},
    {"filename": "SaaS-Subscription-HRPlatform.pdf", "contract_type": "sow", "counterparty": "PeopleFirst Software", "value": Decimal("156000"), "risk": "low", "risk_score": 22, "bu_code": "PROC"},
    {"filename": "Vendor-Agreement-OfficeSupplies.pdf", "contract_type": "vendor_agreement", "counterparty": "SupplyChain Direct", "value": Decimal("78000"), "risk": "low", "risk_score": 12, "bu_code": "PROC"},

    # Legal BU contracts
    {"filename": "NDA-StrategicPartner-2025.pdf", "contract_type": "nda", "counterparty": "Strategic Alliance Group", "value": None, "risk": "low", "risk_score": 10, "bu_code": "LEGAL"},
    {"filename": "NDA-Acquisition-Target.pdf", "contract_type": "nda", "counterparty": "InnovateTech Ltd", "value": None, "risk": "medium", "risk_score": 35, "bu_code": "LEGAL"},
    {"filename": "Settlement-Agreement-IPDispute.pdf", "contract_type": "msa", "counterparty": "PatentHolders LLC", "value": Decimal("2500000"), "risk": "critical", "risk_score": 88, "bu_code": "LEGAL"},
    {"filename": "License-Agreement-Trademark.pdf", "contract_type": "nda", "counterparty": "BrandLicensing Corp", "value": Decimal("180000"), "risk": "medium", "risk_score": 40, "bu_code": "LEGAL"},
    {"filename": "NDA-BoardAdvisor-Confidential.pdf", "contract_type": "nda", "counterparty": "Advisory Board Member", "value": None, "risk": "low", "risk_score": 15, "bu_code": "LEGAL"},

    # Sales BU contracts
    {"filename": "MSA-EnterpriseClient-GlobalBank.pdf", "contract_type": "msa", "counterparty": "Global Banking Corp", "value": Decimal("4200000"), "risk": "high", "risk_score": 65, "bu_code": "SALES"},
    {"filename": "SOW-Implementation-Phase2.pdf", "contract_type": "sow", "counterparty": "Global Banking Corp", "value": Decimal("780000"), "risk": "medium", "risk_score": 42, "bu_code": "SALES-ENT"},
    {"filename": "MSA-MidMarket-RetailChain.pdf", "contract_type": "msa", "counterparty": "RetailChain Holdings", "value": Decimal("520000"), "risk": "medium", "risk_score": 38, "bu_code": "SALES-SMB"},
    {"filename": "Amendment-GlobalBank-PriceAdj.pdf", "contract_type": "amendment", "counterparty": "Global Banking Corp", "value": Decimal("350000"), "risk": "low", "risk_score": 20, "bu_code": "SALES-ENT"},
    {"filename": "SOW-PilotProgram-StartupClient.pdf", "contract_type": "sow", "counterparty": "FastGrow Startup", "value": Decimal("45000"), "risk": "low", "risk_score": 15, "bu_code": "SALES-SMB"},

    # Operations BU contracts
    {"filename": "MSA-DataCenter-Hosting.pdf", "contract_type": "msa", "counterparty": "DataCenter Solutions", "value": Decimal("960000"), "risk": "high", "risk_score": 70, "bu_code": "OPS"},
    {"filename": "SLA-Agreement-NetworkProvider.pdf", "contract_type": "sow", "counterparty": "NetConnect Telecom", "value": Decimal("420000"), "risk": "medium", "risk_score": 48, "bu_code": "OPS"},
    {"filename": "Vendor-Agreement-FacilityMgmt.pdf", "contract_type": "vendor_agreement", "counterparty": "FacilityPro Services", "value": Decimal("195000"), "risk": "low", "risk_score": 20, "bu_code": "OPS"},
    {"filename": "MSA-CloudMigration-Services.pdf", "contract_type": "msa", "counterparty": "CloudShift Consulting", "value": Decimal("1100000"), "risk": "high", "risk_score": 68, "bu_code": "OPS"},

    # Finance BU contracts
    {"filename": "MSA-AuditFirm-Annual.pdf", "contract_type": "msa", "counterparty": "BigFour Audit LLP", "value": Decimal("380000"), "risk": "medium", "risk_score": 35, "bu_code": "FIN"},
    {"filename": "License-Agreement-ERPSystem.pdf", "contract_type": "vendor_agreement", "counterparty": "SAP Enterprise", "value": Decimal("2100000"), "risk": "high", "risk_score": 62, "bu_code": "FIN"},
    {"filename": "Vendor-Agreement-PayrollProvider.pdf", "contract_type": "vendor_agreement", "counterparty": "PayrollPro Inc", "value": Decimal("145000"), "risk": "low", "risk_score": 18, "bu_code": "FIN"},
    {"filename": "NDA-InvestorRelations-2025.pdf", "contract_type": "nda", "counterparty": "Venture Capital Fund III", "value": None, "risk": "low", "risk_score": 12, "bu_code": "FIN"},
    {"filename": "Insurance-Policy-D&O.pdf", "contract_type": "msa", "counterparty": "GlobalInsure Underwriters", "value": Decimal("520000"), "risk": "medium", "risk_score": 40, "bu_code": "FIN"},
]

# Tenants to skip (already have enough contracts)
SKIP_TENANTS = {"cuad-benchmark"}


async def seed_contracts():
    print("=" * 60)
    print("Seeding Additional Contracts")
    print("=" * 60)

    async with async_session_maker() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        for tenant in tenants:
            if tenant.slug in SKIP_TENANTS:
                print(f"\nSkipping {tenant.name} (excluded)")
                continue

            # Count existing contracts
            count_result = await db.execute(
                select(func.count(Contract.id)).where(Contract.tenant_id == tenant.id)
            )
            existing_count = count_result.scalar() or 0

            if existing_count >= MIN_CONTRACTS:
                print(f"\n{tenant.name}: already has {existing_count} contracts, skipping")
                continue

            print(f"\n{tenant.name}: has {existing_count} contracts, seeding more...")
            print("-" * 40)

            # Load BUs for this tenant
            bu_result = await db.execute(
                select(BusinessUnit).where(
                    BusinessUnit.tenant_id == tenant.id,
                    BusinessUnit.is_active == True,
                )
            )
            bus = {bu.code: bu for bu in bu_result.scalars().all()}

            # Get an admin user for uploaded_by
            admin_result = await db.execute(
                select(User).where(
                    User.tenant_id == tenant.id,
                    User.role == Role.ADMIN,
                    User.is_active == True,
                ).limit(1)
            )
            admin_user = admin_result.scalar_one_or_none()
            uploaded_by = admin_user.id if admin_user else None

            needed = MIN_CONTRACTS - existing_count
            templates = CONTRACT_TEMPLATES[:needed]
            created = 0

            for tmpl in templates:
                bu_code = tmpl["bu_code"]
                bu = bus.get(bu_code)
                bu_id = bu.id if bu else None
                bu_name = bu.name if bu else "Unassigned"

                # Randomize dates
                effective = date.today() - timedelta(days=random.randint(30, 365))
                expiration = effective + timedelta(days=random.randint(180, 730))

                contract = Contract(
                    id=uuid4(),
                    filename=tmpl["filename"],
                    file_path=f"/data/contracts/{tmpl['filename']}",
                    contract_type=ContractType(tmpl["contract_type"]),
                    counterparty=tmpl["counterparty"],
                    contract_value=tmpl["value"],
                    currency="USD" if tmpl["value"] else None,
                    risk_level=RiskLevel(tmpl["risk"]),
                    risk_score=tmpl["risk_score"],
                    status=ContractStatus.COMPLETED,
                    effective_date=effective,
                    expiration_date=expiration,
                    tenant_id=tenant.id,
                    business_unit_id=bu_id,
                    uploaded_by=uploaded_by,
                )
                db.add(contract)
                created += 1
                print(f"  + {tmpl['filename'][:45]:47s} -> {bu_name}")

            await db.commit()
            print(f"  Created {created} contracts")

        # Print final summary
        print("\n" + "=" * 60)
        print("FINAL CONTRACT DISTRIBUTION")
        print("=" * 60)

        for tenant in tenants:
            if tenant.slug in SKIP_TENANTS:
                continue

            print(f"\n{tenant.name}:")
            count_result = await db.execute(
                select(
                    BusinessUnit.name,
                    func.count(Contract.id),
                )
                .join(Contract, Contract.business_unit_id == BusinessUnit.id)
                .where(BusinessUnit.tenant_id == tenant.id)
                .group_by(BusinessUnit.name)
                .order_by(BusinessUnit.name)
            )
            total = 0
            for bu_name, count in count_result.all():
                print(f"  {bu_name:20s} {count:3d} contracts")
                total += count

            # Count unassigned
            unassigned_result = await db.execute(
                select(func.count(Contract.id)).where(
                    Contract.tenant_id == tenant.id,
                    Contract.business_unit_id == None,
                )
            )
            unassigned = unassigned_result.scalar() or 0
            if unassigned:
                print(f"  {'(Unassigned)':20s} {unassigned:3d} contracts")
                total += unassigned
            print(f"  {'TOTAL':20s} {total:3d}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_contracts())
