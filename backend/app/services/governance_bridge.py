"""Governance Bridge Service — automatically populates relationship governance
data when contracts are processed.

Called at the end of _run_deep_analysis after all AI agents have completed.
Each automation is independent and fault-tolerant: one failure does not block others.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

from app.models.contract import Contract, ContractType, RiskLevel
from app.models.clause import Clause
from app.models.sla import ContractSLA, SLAMetricType, SLAUnit
from app.models.organization import Organization, OrganizationType, OrganizationLevel
from app.models.party import ContractParty, PartyRole
from app.models.preamble import ContractPreamble, ContractPartyDetail
from app.models.relationship import (
    BusinessRelationship,
    RelationshipType,
    RelationshipStatus,
    GovernanceTier,
)
from app.models.kpi import KPI, KPICategory, KPIMeasurementType
from app.models.improvement import (
    ImprovementPoint,
    ImprovementPriority,
    ImprovementSource,
    ImprovementStatus,
)
from app.models.service_portfolio import ServicePortfolio, RelationshipService, ServiceType

logger = logging.getLogger(__name__)


# ── Metric type → KPI category/measurement mapping ──────────────────────

SLA_TO_KPI_MAP: dict[str, tuple[str, str]] = {
    SLAMetricType.UPTIME_PERCENTAGE.value: (KPICategory.SERVICE_DELIVERY.value, KPIMeasurementType.PERCENTAGE.value),
    SLAMetricType.AVAILABILITY.value: (KPICategory.SERVICE_DELIVERY.value, KPIMeasurementType.PERCENTAGE.value),
    SLAMetricType.RESPONSE_TIME.value: (KPICategory.TIMELINESS.value, KPIMeasurementType.TIME_HOURS.value),
    SLAMetricType.RESOLUTION_TIME.value: (KPICategory.TIMELINESS.value, KPIMeasurementType.TIME_HOURS.value),
    SLAMetricType.DELIVERY_TIME.value: (KPICategory.TIMELINESS.value, KPIMeasurementType.TIME_DAYS.value),
    SLAMetricType.SUCCESS_RATE.value: (KPICategory.COMPLIANCE.value, KPIMeasurementType.PERCENTAGE.value),
    SLAMetricType.ERROR_RATE.value: (KPICategory.QUALITY.value, KPIMeasurementType.PERCENTAGE.value),
    SLAMetricType.COMPLIANCE_RATE.value: (KPICategory.COMPLIANCE.value, KPIMeasurementType.PERCENTAGE.value),
    SLAMetricType.UTILIZATION.value: (KPICategory.SERVICE_DELIVERY.value, KPIMeasurementType.PERCENTAGE.value),
    SLAMetricType.THROUGHPUT.value: (KPICategory.SERVICE_DELIVERY.value, KPIMeasurementType.NUMBER.value),
    SLAMetricType.RECOVERY_TIME.value: (KPICategory.SERVICE_DELIVERY.value, KPIMeasurementType.TIME_HOURS.value),
    SLAMetricType.RECOVERY_POINT.value: (KPICategory.SERVICE_DELIVERY.value, KPIMeasurementType.TIME_HOURS.value),
    SLAMetricType.QUALITY_SCORE.value: (KPICategory.QUALITY.value, KPIMeasurementType.RATING.value),
    SLAMetricType.CUSTOM.value: (KPICategory.OTHER.value, KPIMeasurementType.NUMBER.value),
}

# ── Contract type → default org type mapping ─────────────────────────────

CONTRACT_TYPE_TO_ORG: dict[str, str] = {
    ContractType.MSA.value: OrganizationType.CUSTOMER.value,
    ContractType.SOW.value: OrganizationType.CUSTOMER.value,
    ContractType.NDA.value: OrganizationType.PARTNER.value,
    ContractType.VENDOR_AGREEMENT.value: OrganizationType.VENDOR.value,
    ContractType.AMENDMENT.value: OrganizationType.CUSTOMER.value,
}

# ── High-risk clause types that warrant improvement points ───────────────

HIGH_RISK_CLAUSE_LABELS: dict[str, str] = {
    "indemnification": "Broad Indemnification",
    "limitation_of_liability": "Weak Liability Protection",
    "termination": "Unfavorable Termination Terms",
    "intellectual_property": "IP Ownership Risk",
    "confidentiality": "Weak Confidentiality",
    "auto_renewal": "Auto-Renewal Trap",
    "data_protection": "Data Protection Gap",
    "force_majeure": "Missing Force Majeure Protection",
}


class GovernanceBridgeService:
    """Bridges contract intelligence to relationship governance."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def bridge_contract_to_governance(
        self,
        contract_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> dict:
        """Run all governance bridge automations for a completed contract.

        Returns a summary dict of what was created/linked.
        """
        summary: dict = {
            "org_matched": None,
            "org_created": False,
            "relationship_matched": None,
            "relationship_created": False,
            "kpis_created": 0,
            "improvements_created": 0,
            "health_score": None,
            "services_linked": 0,
            "errors": [],
        }

        # Load contract with SLAs and clauses
        result = await self.db.execute(
            select(Contract).where(Contract.id == contract_id)
        )
        contract = result.scalar_one_or_none()
        if not contract:
            summary["errors"].append("Contract not found")
            return summary

        # Skip employment contracts — no B2B governance
        if contract.contract_type == ContractType.EMPLOYMENT_CONTRACT:
            return summary

        # ── Automation 1: Counterparty → Organization ────────────────
        org = None
        try:
            org = await self._match_or_create_organization(contract, tenant_id)
            if org:
                summary["org_matched"] = str(org.id)
                summary["org_created"] = org in self.db.new
        except Exception as e:
            logger.warning(f"Governance bridge: org matching failed: {e}")
            summary["errors"].append(f"org_match: {e}")

        if not org:
            return summary  # Can't proceed without an org

        # ── Automation 2: Contract → Business Relationship ───────────
        relationship = None
        try:
            relationship = await self._find_or_create_relationship(
                contract, org, tenant_id
            )
            if relationship:
                summary["relationship_matched"] = str(relationship.id)
                summary["relationship_created"] = relationship in self.db.new
        except Exception as e:
            logger.warning(f"Governance bridge: relationship linking failed: {e}")
            summary["errors"].append(f"relationship: {e}")

        if not relationship:
            return summary  # Can't create KPIs/improvements without a relationship

        # Flush org + relationship before creating dependent records
        await self.db.flush()

        # ── Automation 3: SLA → KPI ──────────────────────────────────
        try:
            kpis = await self._create_kpis_from_slas(contract, relationship)
            summary["kpis_created"] = len(kpis)
        except Exception as e:
            logger.warning(f"Governance bridge: KPI creation failed: {e}")
            summary["errors"].append(f"kpis: {e}")

        # ── Automation 4: Risk → Improvement Points ──────────────────
        try:
            improvements = await self._create_improvements_from_risks(
                contract, relationship
            )
            summary["improvements_created"] = len(improvements)
        except Exception as e:
            logger.warning(f"Governance bridge: improvement creation failed: {e}")
            summary["errors"].append(f"improvements: {e}")

        # ── Automation 5: Health Score ────────────────────────────────
        try:
            score = await self._calculate_health_score(relationship, contract)
            summary["health_score"] = score
        except Exception as e:
            logger.warning(f"Governance bridge: health score failed: {e}")
            summary["errors"].append(f"health_score: {e}")

        # ── Automation 7: SOW services → Service Portfolio ───────────
        try:
            links = await self._link_sow_services(
                contract, relationship, org, tenant_id
            )
            summary["services_linked"] = len(links)
        except Exception as e:
            logger.warning(f"Governance bridge: service linking failed: {e}")
            summary["errors"].append(f"services: {e}")

        await self.db.flush()
        return summary

    # ── Automation 1 ─────────────────────────────────────────────────────

    async def _match_or_create_organization(
        self,
        contract: Contract,
        tenant_id: uuid.UUID,
    ) -> Optional[Organization]:
        """Match counterparty to an existing Organization or create one."""
        counterparty = (contract.counterparty or "").strip()
        if not counterparty:
            return None

        # Exact case-insensitive match
        result = await self.db.execute(
            select(Organization).where(
                Organization.tenant_id == tenant_id,
                func.lower(Organization.name) == counterparty.lower(),
            )
        )
        org = result.scalar_one_or_none()
        if org:
            return org

        # Fuzzy match: org name contains counterparty or vice versa
        result = await self.db.execute(
            select(Organization).where(
                Organization.tenant_id == tenant_id,
                or_(
                    func.lower(Organization.name).contains(counterparty.lower()),
                    func.lower(func.cast(counterparty, String)).op("LIKE")(
                        "%" + func.lower(Organization.name) + "%"
                    ) if False else  # SQLAlchemy doesn't support this cleanly
                    Organization.name.ilike(f"%{counterparty[:10]}%"),
                ),
            )
        )
        org = result.scalar_one_or_none()
        if org:
            return org

        # Determine the counterparty's role using AI-extracted data
        org_type = await self._determine_counterparty_role(contract)

        code = self._generate_org_code(counterparty)
        # Ensure code is unique
        for attempt in range(5):
            candidate = code if attempt == 0 else f"{code}{attempt}"
            existing = await self.db.execute(
                select(Organization.id).where(Organization.code == candidate)
            )
            if not existing.scalar_one_or_none():
                code = candidate
                break

        # Gather enrichment data from AI extraction
        enrichment = await self._extract_org_details(contract, counterparty)

        # If key fields are still missing, use AI to extract them
        needs_ai = (
            not enrichment.get("country")
            or not enrichment.get("industry")
        )
        if needs_ai:
            ai_data = await self._ai_extract_org_info(contract, counterparty)
            if ai_data:
                # AI can also correct the org_type
                if ai_data.get("org_type"):
                    org_type = ai_data.pop("org_type")
                # Merge AI data without overwriting existing values
                for key, val in ai_data.items():
                    if val and not enrichment.get(key):
                        enrichment[key] = val

        org = Organization(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=counterparty,
            code=code,
            org_type=org_type,
            organization_level=None,
            is_active=True,
            **enrichment,
        )
        self.db.add(org)
        return org

    async def _determine_counterparty_role(
        self, contract: Contract
    ) -> str:
        """Determine if the counterparty is a vendor, customer, or partner.

        Uses multiple signals in priority order:
        1. ContractParty table (explicit roles from AI extraction)
        2. ContractPartyDetail from preamble (party_role field)
        3. Contract text analysis (looks for role labels near party names)
        4. Contract type mapping (fallback)
        """
        counterparty = (contract.counterparty or "").strip().lower()

        # ── Signal 1: ContractParty table ─────────────────────────────────
        result = await self.db.execute(
            select(ContractParty).where(
                ContractParty.contract_id == contract.id,
                ContractParty.is_primary == False,
            )
        )
        parties = result.scalars().all()
        for party in parties:
            if party.legal_name and counterparty in party.legal_name.lower():
                role_map = {
                    PartyRole.VENDOR: OrganizationType.VENDOR.value,
                    PartyRole.PROVIDER: OrganizationType.VENDOR.value,
                    PartyRole.CUSTOMER: OrganizationType.CUSTOMER.value,
                    PartyRole.CLIENT: OrganizationType.CUSTOMER.value,
                    PartyRole.LICENSOR: OrganizationType.VENDOR.value,
                    PartyRole.LICENSEE: OrganizationType.CUSTOMER.value,
                    PartyRole.DISCLOSING_PARTY: OrganizationType.PARTNER.value,
                    PartyRole.RECEIVING_PARTY: OrganizationType.PARTNER.value,
                }
                if party.role in role_map:
                    logger.info(f"Org type from ContractParty role: {party.role.value} → {role_map[party.role]}")
                    return role_map[party.role]

        # ── Signal 2: Preamble party details ──────────────────────────────
        result = await self.db.execute(
            select(ContractPartyDetail)
            .join(ContractPreamble, ContractPartyDetail.preamble_id == ContractPreamble.id)
            .where(ContractPreamble.contract_id == contract.id)
        )
        preamble_parties = result.scalars().all()
        for pp in preamble_parties:
            if pp.party_name and counterparty in pp.party_name.lower():
                role_text = (pp.party_role or "").lower()
                if any(kw in role_text for kw in ["vendor", "provider", "supplier", "licensor"]):
                    logger.info(f"Org type from preamble party_role: {pp.party_role} → vendor")
                    return OrganizationType.VENDOR.value
                if any(kw in role_text for kw in ["customer", "client", "buyer", "licensee"]):
                    logger.info(f"Org type from preamble party_role: {pp.party_role} → customer")
                    return OrganizationType.CUSTOMER.value

        # ── Signal 3: Contract text analysis ──────────────────────────────
        text = (contract.extracted_text or "")[:3000].lower()
        if text and counterparty:
            # Find counterparty position in text
            cp_pos = text.find(counterparty[:30].lower())
            if cp_pos == -1:
                # Try shorter prefix
                cp_pos = text.find(counterparty[:15].lower())

            if cp_pos != -1:
                # Look at surrounding context (500 chars around the mention)
                start = max(0, cp_pos - 200)
                end = min(len(text), cp_pos + len(counterparty) + 200)
                context = text[start:end]

                # Check for role labels near the counterparty name
                vendor_signals = ["vendor", "provider", "supplier", "service provider"]
                customer_signals = ["customer", "client", "buyer", "purchaser"]
                partner_signals = ["partner", "collaborator"]

                vendor_score = sum(1 for kw in vendor_signals if kw in context)
                customer_score = sum(1 for kw in customer_signals if kw in context)
                partner_score = sum(1 for kw in partner_signals if kw in context)

                if vendor_score > customer_score and vendor_score > partner_score:
                    logger.info(f"Org type from text analysis: vendor (score {vendor_score})")
                    return OrganizationType.VENDOR.value
                if customer_score > vendor_score and customer_score > partner_score:
                    logger.info(f"Org type from text analysis: customer (score {customer_score})")
                    return OrganizationType.CUSTOMER.value
                if partner_score > 0:
                    logger.info(f"Org type from text analysis: partner (score {partner_score})")
                    return OrganizationType.PARTNER.value

            # Also check schema_data reference_text for role clues
            if contract.schema_data and isinstance(contract.schema_data, dict):
                refs = contract.schema_data.get("_contract_references", {})
                ref_text = ""
                for pref in refs.get("parent_references", []):
                    ref_text += " " + (pref.get("reference_text", "") or "")
                ref_text = ref_text.lower()
                if ref_text:
                    vendor_hit = any(kw in ref_text for kw in ["vendor", "provider", "supplier"])
                    customer_hit = any(kw in ref_text for kw in ["customer", "client", "buyer"])
                    if vendor_hit and not customer_hit:
                        logger.info("Org type from schema_data reference_text: vendor")
                        return OrganizationType.VENDOR.value
                    if customer_hit and not vendor_hit:
                        logger.info("Org type from schema_data reference_text: customer")
                        return OrganizationType.CUSTOMER.value

        # ── Signal 4: Contract type mapping (fallback) ────────────────────
        org_type = CONTRACT_TYPE_TO_ORG.get(
            contract.contract_type.value if contract.contract_type else "",
            OrganizationType.CUSTOMER.value,
        )
        logger.info(f"Org type from contract_type fallback: {org_type}")
        return org_type

    async def _extract_org_details(
        self, contract: Contract, counterparty: str
    ) -> dict:
        """Extract organization details from AI-extracted contract data.

        Returns a dict of Organization fields to set.
        """
        details: dict = {}
        counterparty_lower = counterparty.lower()

        # ── From ContractParty table ──────────────────────────────────────
        result = await self.db.execute(
            select(ContractParty).where(
                ContractParty.contract_id == contract.id,
            )
        )
        parties = result.scalars().all()
        for party in parties:
            if party.legal_name and counterparty_lower in party.legal_name.lower():
                if party.jurisdiction and not details.get("country"):
                    details["country"] = party.jurisdiction
                if party.registered_address and not details.get("address"):
                    details["address"] = party.registered_address
                if party.entity_type and not details.get("notes"):
                    details["notes"] = f"Entity type: {party.entity_type}"
                if party.contact_name and not details.get("primary_contact_name"):
                    details["primary_contact_name"] = party.contact_name
                if party.contact_email and not details.get("primary_contact_email"):
                    details["primary_contact_email"] = party.contact_email
                break

        # ── From preamble party details ───────────────────────────────────
        result = await self.db.execute(
            select(ContractPartyDetail)
            .join(ContractPreamble, ContractPartyDetail.preamble_id == ContractPreamble.id)
            .where(ContractPreamble.contract_id == contract.id)
        )
        preamble_parties = result.scalars().all()
        for pp in preamble_parties:
            if pp.party_name and counterparty_lower in pp.party_name.lower():
                if pp.jurisdiction_of_incorporation and not details.get("country"):
                    details["country"] = pp.jurisdiction_of_incorporation
                if pp.address and not details.get("address"):
                    details["address"] = pp.address
                if pp.legal_form and not details.get("notes"):
                    details["notes"] = f"Legal form: {pp.legal_form}"
                break

        # ── Infer region from country ─────────────────────────────────────
        if details.get("country") and not details.get("region"):
            country = details["country"].lower()
            region_map = {
                "india": "Asia Pacific", "japan": "Asia Pacific", "china": "Asia Pacific",
                "australia": "Asia Pacific", "singapore": "Asia Pacific", "korea": "Asia Pacific",
                "united states": "North America", "usa": "North America", "canada": "North America",
                "united kingdom": "Europe", "uk": "Europe", "germany": "Europe",
                "france": "Europe", "netherlands": "Europe", "switzerland": "Europe",
                "ireland": "Europe", "spain": "Europe", "italy": "Europe",
                "brazil": "Latin America", "mexico": "Latin America",
                "uae": "Middle East", "saudi arabia": "Middle East",
                "south africa": "Africa", "nigeria": "Africa",
            }
            for key, region in region_map.items():
                if key in country:
                    details["region"] = region
                    break

        # ── Infer industry from contract context ──────────────────────────
        if not details.get("industry") and contract.extracted_text:
            text_sample = contract.extracted_text[:2000].lower()
            industry_keywords = {
                "Technology": ["software", "technology", "saas", "cloud", "platform", "digital", "it services"],
                "Financial Services": ["banking", "financial", "investment", "insurance", "fintech"],
                "Healthcare": ["healthcare", "medical", "pharmaceutical", "biotech", "hospital"],
                "Manufacturing": ["manufacturing", "production", "industrial", "factory"],
                "Professional Services": ["consulting", "advisory", "professional services", "managed services"],
                "Telecommunications": ["telecom", "telecommunications", "wireless", "network"],
                "Energy": ["energy", "oil", "gas", "renewable", "power"],
                "Retail": ["retail", "commerce", "consumer goods"],
                "Legal": ["legal", "law firm", "attorney"],
            }
            best_industry = None
            best_score = 0
            for industry, keywords in industry_keywords.items():
                score = sum(1 for kw in keywords if kw in text_sample)
                if score > best_score:
                    best_score = score
                    best_industry = industry
            if best_industry and best_score >= 2:
                details["industry"] = best_industry

        return details

    async def _ai_extract_org_info(
        self, contract: Contract, counterparty: str
    ) -> Optional[dict]:
        """Use GPT to extract organization details from contract text.

        Called when structured data (ContractParty, preamble) is unavailable.
        Returns dict with org_type, industry, country, region fields.
        """
        text_sample = (contract.extracted_text or "")[:3000]
        if not text_sample or len(text_sample) < 100:
            return None

        try:
            client = AsyncOpenAI(api_key=settings.openai_api_key)

            prompt = f"""Analyze this contract text and determine the following about the counterparty "{counterparty}":

1. **role**: Is "{counterparty}" the vendor/provider/supplier, the customer/client/buyer, or a partner? Answer one of: vendor, customer, partner
2. **industry**: What industry does "{counterparty}" operate in? (e.g. Technology, Financial Services, Healthcare, Manufacturing, Professional Services, Education, Government, Non-Profit, Legal, Real Estate, Consulting, Telecommunications, Energy, Retail)
3. **country**: What country is "{counterparty}" based in? Use full country name.
4. **region**: What region? (North America, Europe, Asia Pacific, Latin America, Middle East, Africa)

Contract text (first 3000 chars):
---
{text_sample}
---

Respond ONLY with valid JSON, no markdown:
{{"role": "vendor|customer|partner", "industry": "...", "country": "...", "region": "..."}}

If you cannot determine a field, use null for that field."""

            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            )

            content = (response.choices[0].message.content or "").strip()
            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            data = json.loads(content)
            result = {}

            # Map role to org_type
            role = (data.get("role") or "").lower()
            role_map = {
                "vendor": OrganizationType.VENDOR.value,
                "provider": OrganizationType.VENDOR.value,
                "supplier": OrganizationType.VENDOR.value,
                "customer": OrganizationType.CUSTOMER.value,
                "client": OrganizationType.CUSTOMER.value,
                "partner": OrganizationType.PARTNER.value,
            }
            if role in role_map:
                result["org_type"] = role_map[role]

            if data.get("industry"):
                result["industry"] = data["industry"]
            if data.get("country"):
                result["country"] = data["country"]
            if data.get("region"):
                result["region"] = data["region"]

            logger.info(f"AI org extraction for '{counterparty}': {result}")
            return result

        except Exception as e:
            logger.warning(f"AI org extraction failed for '{counterparty}': {e}")
            return None

    @staticmethod
    def _generate_org_code(name: str) -> str:
        """Generate a short code from org name (e.g. 'Acme Corporation' → 'ACME')."""
        # Take first letters of each word, up to 6 chars
        words = re.sub(r"[^a-zA-Z0-9\s]", "", name).split()
        if len(words) == 1:
            return words[0][:6].upper()
        return "".join(w[0] for w in words[:6]).upper()

    # ── Automation 2 ─────────────────────────────────────────────────────

    async def _find_or_create_relationship(
        self,
        contract: Contract,
        counterparty_org: Organization,
        tenant_id: uuid.UUID,
    ) -> Optional[BusinessRelationship]:
        """Find or create a BusinessRelationship and link the contract to it."""
        # Find the internal org for this tenant
        result = await self.db.execute(
            select(Organization).where(
                Organization.tenant_id == tenant_id,
                Organization.org_type == OrganizationType.INTERNAL.value,
            ).limit(1)
        )
        internal_org = result.scalar_one_or_none()
        if not internal_org:
            logger.warning(
                f"No internal organization found for tenant {tenant_id}. "
                "Create one to enable automatic relationship linking."
            )
            return None

        # Don't link to ourselves
        if internal_org.id == counterparty_org.id:
            return None

        # Look for existing relationship (either direction)
        result = await self.db.execute(
            select(BusinessRelationship).where(
                BusinessRelationship.tenant_id == tenant_id,
                or_(
                    (BusinessRelationship.org_a_id == internal_org.id)
                    & (BusinessRelationship.org_b_id == counterparty_org.id),
                    (BusinessRelationship.org_a_id == counterparty_org.id)
                    & (BusinessRelationship.org_b_id == internal_org.id),
                ),
            )
        )
        relationship = result.scalar_one_or_none()

        if not relationship:
            # Infer relationship type from org type
            rel_type_map = {
                OrganizationType.CUSTOMER.value: RelationshipType.CUSTOMER.value,
                OrganizationType.VENDOR.value: RelationshipType.SUPPLIER.value,
                OrganizationType.PARTNER.value: RelationshipType.PARTNER.value,
            }
            rel_type = rel_type_map.get(
                counterparty_org.org_type,
                RelationshipType.CUSTOMER.value,
            )

            relationship = BusinessRelationship(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                org_a_id=internal_org.id,
                org_b_id=counterparty_org.id,
                relationship_type=rel_type,
                status=RelationshipStatus.ACTIVE.value,
                governance_tier=GovernanceTier.OPERATIONAL.value,
                name=f"{counterparty_org.name} - {rel_type.replace('_', ' ').title()}",
                start_date=contract.effective_date or datetime.utcnow(),
                review_frequency_days=90,
            )
            self.db.add(relationship)

        # Link contract to relationship
        contract.business_relationship_id = relationship.id
        return relationship

    # ── Automation 3 ─────────────────────────────────────────────────────

    async def _create_kpis_from_slas(
        self,
        contract: Contract,
        relationship: BusinessRelationship,
    ) -> list:
        """Create KPI records from extracted SLAs."""
        # Load SLAs for this contract
        result = await self.db.execute(
            select(ContractSLA).where(
                ContractSLA.contract_id == contract.id,
                ContractSLA.is_active == True,
            )
        )
        slas = result.scalars().all()
        if not slas:
            return []

        # Load existing KPIs for this relationship to avoid duplicates
        result = await self.db.execute(
            select(KPI).where(KPI.relationship_id == relationship.id)
        )
        existing_kpis = result.scalars().all()
        existing_names = {k.name.lower() for k in existing_kpis}

        created = []
        for sla in slas:
            # Skip if a KPI with same name already exists
            if sla.sla_name.lower() in existing_names:
                continue

            # Map metric type to KPI category and measurement type
            metric_key = sla.metric_type.value if hasattr(sla.metric_type, 'value') else str(sla.metric_type)
            category, measurement = SLA_TO_KPI_MAP.get(
                metric_key,
                (KPICategory.OTHER.value, KPIMeasurementType.NUMBER.value),
            )

            # Generate code from SLA name
            code = self._generate_kpi_code(sla.sla_name)

            kpi = KPI(
                id=uuid.uuid4(),
                relationship_id=relationship.id,
                name=sla.sla_name,
                code=code,
                description=sla.sla_description or f"Auto-generated from contract SLA in {contract.filename}",
                category=category,
                measurement_type=measurement,
                target_value=sla.target_value,
                minimum_value=sla.warning_threshold,
                threshold_amber=sla.warning_threshold,
                weight=Decimal("1.0"),
                is_active=True,
                is_perception_based=False,  # Metric-based from SLA, not perception
            )
            self.db.add(kpi)
            created.append(kpi)
            existing_names.add(sla.sla_name.lower())

        return created

    @staticmethod
    def _generate_kpi_code(name: str) -> str:
        """Generate KPI code from name (e.g. 'System Uptime' → 'SU')."""
        words = re.sub(r"[^a-zA-Z0-9\s]", "", name).split()
        if len(words) == 1:
            return words[0][:4].upper()
        return "".join(w[0] for w in words[:5]).upper()

    # ── Automation 4 ─────────────────────────────────────────────────────

    async def _create_improvements_from_risks(
        self,
        contract: Contract,
        relationship: BusinessRelationship,
    ) -> list:
        """Create improvement points from high-risk clauses."""
        # Load high/critical risk clauses
        result = await self.db.execute(
            select(Clause).where(
                Clause.contract_id == contract.id,
                Clause.risk_level.in_([RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]),
            )
        )
        risky_clauses = result.scalars().all()
        if not risky_clauses:
            return []

        # Check for existing improvements to avoid duplicates
        result = await self.db.execute(
            select(ImprovementPoint.title).where(
                ImprovementPoint.relationship_id == relationship.id,
                ImprovementPoint.source == ImprovementSource.CONTRACT_RISK.value,
            )
        )
        existing_titles = {row[0].lower() for row in result.all()}

        created = []
        for clause in risky_clauses:
            clause_type_val = clause.clause_type.value if hasattr(clause.clause_type, 'value') else str(clause.clause_type)
            label = HIGH_RISK_CLAUSE_LABELS.get(clause_type_val, clause_type_val.replace("_", " ").title())
            title = f"Contract Risk: {label}"

            if title.lower() in existing_titles:
                continue

            risk_level_val = clause.risk_level.value if hasattr(clause.risk_level, 'value') else str(clause.risk_level)
            priority = (
                ImprovementPriority.CRITICAL.value
                if risk_level_val == RiskLevel.CRITICAL.value
                else ImprovementPriority.HIGH.value
            )

            # Extract a brief description from clause text
            clause_preview = (clause.text or "")[:300]
            description = (
                f"High-risk {label.lower()} clause detected in '{contract.filename}'. "
                f"Review and renegotiate during next renewal cycle.\n\n"
                f"Clause excerpt: \"{clause_preview}...\""
            )

            improvement = ImprovementPoint(
                id=uuid.uuid4(),
                relationship_id=relationship.id,
                title=title,
                description=description,
                source=ImprovementSource.CONTRACT_RISK.value,
                priority=priority,
                status=ImprovementStatus.OPEN.value,
                target_outcome=f"Renegotiate {label.lower()} terms to reduce contract risk",
            )
            self.db.add(improvement)
            created.append(improvement)
            existing_titles.add(title.lower())

        return created

    # ── Automation 5 ─────────────────────────────────────────────────────

    async def _calculate_health_score(
        self,
        relationship: BusinessRelationship,
        contract: Contract,
    ) -> Optional[int]:
        """Calculate composite health score for the relationship."""
        components = []

        # Component 1: Contract risk (weight 30%)
        # Invert risk score: low risk = high health
        if contract.risk_score is not None:
            risk_health = 100 - contract.risk_score
            components.append(("risk", risk_health, 0.3))

        # Component 2: SLA compliance (weight 40%)
        # Average current_compliance_rate across all SLAs for contracts in this relationship
        sla_result = await self.db.execute(
            select(func.avg(ContractSLA.current_compliance_rate)).where(
                ContractSLA.contract_id.in_(
                    select(Contract.id).where(
                        Contract.business_relationship_id == relationship.id
                    )
                ),
                ContractSLA.is_active == True,
                ContractSLA.current_compliance_rate.isnot(None),
            )
        )
        avg_compliance = sla_result.scalar()
        if avg_compliance is not None:
            components.append(("sla", float(avg_compliance), 0.4))

        # Component 3: Obligation health (weight 30%)
        # Based on proportion of green vs amber/red obligations
        from app.models.obligation import Obligation
        rag_result = await self.db.execute(
            select(
                Obligation.rag_status,
                func.count(Obligation.id),
            ).where(
                Obligation.contract_id.in_(
                    select(Contract.id).where(
                        Contract.business_relationship_id == relationship.id
                    )
                ),
            ).group_by(Obligation.rag_status)
        )
        rag_counts = {row[0]: row[1] for row in rag_result.all()}
        total_obligations = sum(rag_counts.values())
        if total_obligations > 0:
            # Score: green=100, amber=50, red=0, not_assessed=75
            score_map = {"green": 100, "amber": 50, "red": 0, "not_assessed": 75}
            weighted_sum = sum(
                score_map.get(status, 75) * count
                for status, count in rag_counts.items()
            )
            obligation_health = weighted_sum / total_obligations
            components.append(("obligation", obligation_health, 0.3))

        if not components:
            # No data yet — set a neutral default
            score = 75
        else:
            # Normalize weights to sum to 1.0
            total_weight = sum(w for _, _, w in components)
            score = round(
                sum(val * (w / total_weight) for _, val, w in components)
            )

        relationship.health_score = max(0, min(100, score))
        relationship.last_health_calculation = datetime.utcnow()
        return relationship.health_score

    # ── Automation 7 ─────────────────────────────────────────────────────

    async def _link_sow_services(
        self,
        contract: Contract,
        relationship: BusinessRelationship,
        counterparty_org: Organization,
        tenant_id: uuid.UUID,
    ) -> list:
        """Link SOW service descriptions to Service Portfolio entries."""
        if not contract.contract_type or contract.contract_type != ContractType.SOW:
            return []

        # Try to get service descriptions from schema_data or clauses
        service_names = []

        # Check schema_data for service line items
        if contract.schema_data and isinstance(contract.schema_data, dict):
            services = contract.schema_data.get("services", {})
            if isinstance(services, dict):
                for item in services.get("line_items", []):
                    if isinstance(item, dict) and item.get("name"):
                        service_names.append(item["name"])

        # Fallback: extract from SERVICE_DESCRIPTION clauses
        if not service_names:
            result = await self.db.execute(
                select(Clause.text).where(
                    Clause.contract_id == contract.id,
                    Clause.clause_type.in_(["service_description", "scope"]),
                ).limit(3)
            )
            for row in result.all():
                if row[0]:
                    # Use the first line as a service name
                    first_line = row[0].strip().split("\n")[0][:100]
                    service_names.append(first_line)

        if not service_names:
            return []

        created = []
        for svc_name in service_names[:5]:  # Cap at 5
            # Fuzzy match against existing portfolio entries
            result = await self.db.execute(
                select(ServicePortfolio).where(
                    ServicePortfolio.tenant_id == tenant_id,
                    ServicePortfolio.name.ilike(f"%{svc_name[:20]}%"),
                ).limit(1)
            )
            portfolio = result.scalar_one_or_none()

            if not portfolio:
                continue  # Don't auto-create portfolios, just link existing ones

            # Check if link already exists
            existing = await self.db.execute(
                select(RelationshipService.id).where(
                    RelationshipService.relationship_id == relationship.id,
                    RelationshipService.service_portfolio_id == portfolio.id,
                )
            )
            if existing.scalar_one_or_none():
                continue

            link = RelationshipService(
                id=uuid.uuid4(),
                relationship_id=relationship.id,
                service_portfolio_id=portfolio.id,
                scope=f"Per SOW: {contract.filename}",
                start_date=contract.effective_date or datetime.utcnow(),
                end_date=contract.expiration_date,
                is_active=True,
            )
            self.db.add(link)
            created.append(link)

        return created


# Need String for func.cast — import at module level
from sqlalchemy import String
