"""Compliance Gap Detection Service.

Checks contracts against industry compliance rules and identifies missing
compliance documents. Creates ComplianceGap records for missing documents
and suggests potential matching documents.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.compliance_gap import ComplianceGap
from app.models.compliance_rule import IndustryComplianceRule
from app.models.contract import Contract
from app.models.contract_link import ContractLink, LinkType
from app.models.industry import (
    ComplianceDocumentType,
    ComplianceGapSeverity,
    ComplianceGapStatus,
    Industry,
)
from app.services.industry_detector import IndustryDetector, IndustryDetectionResult

logger = logging.getLogger(__name__)


# Default resolution deadlines by severity (in days)
SEVERITY_DEADLINES = {
    ComplianceGapSeverity.CRITICAL: 7,
    ComplianceGapSeverity.HIGH: 30,
    ComplianceGapSeverity.MEDIUM: 60,
    ComplianceGapSeverity.LOW: 90,
}


# Map compliance document types to likely contract types (string codes)
DOCUMENT_TYPE_TO_CONTRACT_TYPE: dict[ComplianceDocumentType, list[str]] = {
    ComplianceDocumentType.QUALITY_AGREEMENT: ["vendor_agreement", "quality_agreement"],
    ComplianceDocumentType.PHARMACOVIGILANCE_AGREEMENT: ["vendor_agreement", "pharmacovigilance"],
    ComplianceDocumentType.BAA: ["vendor_agreement", "msa"],
    ComplianceDocumentType.DPA: ["vendor_agreement", "msa"],
    ComplianceDocumentType.PRODUCT_SPECIFICATIONS: ["sow"],
    ComplianceDocumentType.SAFETY_DATA_SHEET: ["vendor_agreement", "supply_agreement"],
    ComplianceDocumentType.SECURITY_ADDENDUM: ["msa", "amendment"],
}


# Keywords that might indicate a document is of a certain compliance type
DOCUMENT_TYPE_KEYWORDS: dict[ComplianceDocumentType, list[str]] = {
    ComplianceDocumentType.QUALITY_AGREEMENT: [
        "quality agreement", "quality assurance", "qa agreement",
        "supplier quality", "manufacturing quality",
    ],
    ComplianceDocumentType.PHARMACOVIGILANCE_AGREEMENT: [
        "pharmacovigilance", "safety data exchange", "adverse event",
        "sdea", "pva", "drug safety",
    ],
    ComplianceDocumentType.BAA: [
        "business associate agreement", "baa", "hipaa",
        "protected health information", "phi",
    ],
    ComplianceDocumentType.DPA: [
        "data processing agreement", "dpa", "gdpr",
        "data protection", "personal data", "controller", "processor",
    ],
    ComplianceDocumentType.PRODUCT_SPECIFICATIONS: [
        "product specification", "technical specification",
        "product requirements", "specs",
    ],
    ComplianceDocumentType.SAFETY_DATA_SHEET: [
        "safety data sheet", "sds", "msds",
        "material safety",
    ],
    ComplianceDocumentType.SECURITY_ADDENDUM: [
        "security addendum", "information security", "cybersecurity",
        "security agreement", "security terms",
    ],
}


@dataclass
class MatchingDocument:
    """A document that potentially resolves a compliance gap."""
    contract: Contract
    match_score: float
    match_reason: str


@dataclass
class ComplianceCheckResult:
    """Result of a compliance check on a contract."""
    contract_id: UUID
    industry: Industry
    industry_confidence: float
    gaps_found: list[ComplianceGap] = field(default_factory=list)
    compliance_score: int = 100  # 0-100, 100 = fully compliant
    total_rules_checked: int = 0
    rules_satisfied: int = 0


class ComplianceGapDetector:
    """Service for detecting compliance gaps in contracts."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self._industry_detector: Optional[IndustryDetector] = None

    @property
    def industry_detector(self) -> IndustryDetector:
        """Lazy-load industry detector."""
        if self._industry_detector is None:
            self._industry_detector = IndustryDetector(self.db)
        return self._industry_detector

    async def check_compliance(
        self,
        contract: Contract,
        industry: Optional[Industry] = None,
        create_gaps: bool = True,
    ) -> ComplianceCheckResult:
        """Check a contract for compliance gaps.

        Args:
            contract: The contract to check.
            industry: Override industry (if not provided, will detect).
            create_gaps: Whether to create ComplianceGap records in the database.

        Returns:
            ComplianceCheckResult with gaps and compliance score.
        """
        # 1. Determine industry
        if industry:
            industry_result = IndustryDetectionResult(
                industry=industry,
                confidence=1.0,
                reasoning="Industry provided explicitly",
            )
        else:
            industry_result = await self.industry_detector.detect_industry(contract)

        detected_industry = industry_result.industry
        industry_confidence = industry_result.confidence

        logger.info(
            f"Checking compliance for contract {contract.id}, "
            f"industry={detected_industry.value}, confidence={industry_confidence:.2f}"
        )

        # 2. Load applicable rules
        rules = await self._load_applicable_rules(
            detected_industry,
            contract.contract_type,
        )

        if not rules:
            logger.info(f"No compliance rules found for {detected_industry.value}/{contract.contract_type}")
            return ComplianceCheckResult(
                contract_id=contract.id,
                industry=detected_industry,
                industry_confidence=industry_confidence,
                compliance_score=100,
                total_rules_checked=0,
                rules_satisfied=0,
            )

        # 3. Check which required documents exist
        linked_contracts = await self._get_linked_contracts(contract)
        existing_doc_types = await self._identify_document_types(linked_contracts)

        # 4. Identify gaps
        gaps: list[ComplianceGap] = []
        rules_satisfied = 0

        for rule in rules:
            if rule.required_document_type in existing_doc_types:
                rules_satisfied += 1
                continue

            # Check if the rule condition applies
            if rule.condition_description:
                if not self._condition_applies(contract, rule.condition_description):
                    rules_satisfied += 1  # Condition doesn't apply, so rule is satisfied
                    continue

            # Create gap
            gap = ComplianceGap(
                contract_id=contract.id,
                rule_id=rule.id,
                missing_document_type=rule.required_document_type,
                gap_description=self._build_gap_description(rule),
                regulatory_reference=rule.regulatory_reference,
                severity=rule.severity_if_missing,
                status=ComplianceGapStatus.OPEN,
                resolution_due_date=self._calculate_due_date(rule.severity_if_missing),
                detection_confidence=industry_confidence,
                detection_reasoning=industry_result.reasoning,
                detected_at=datetime.utcnow(),
            )
            gaps.append(gap)

        # 5. Calculate compliance score
        total_rules = len(rules)
        compliance_score = int((rules_satisfied / total_rules) * 100) if total_rules > 0 else 100

        # 6. Save gaps to database if requested
        if create_gaps and gaps:
            for gap in gaps:
                self.db.add(gap)
            await self.db.flush()
            logger.info(f"Created {len(gaps)} compliance gaps for contract {contract.id}")

        return ComplianceCheckResult(
            contract_id=contract.id,
            industry=detected_industry,
            industry_confidence=industry_confidence,
            gaps_found=gaps,
            compliance_score=compliance_score,
            total_rules_checked=total_rules,
            rules_satisfied=rules_satisfied,
        )

    async def find_matching_documents(
        self,
        contract: Contract,
        required_doc_type: ComplianceDocumentType,
        limit: int = 5,
    ) -> list[MatchingDocument]:
        """Find documents that might resolve a compliance gap.

        Searches for contracts with:
        - Same counterparty
        - Document type that matches the required compliance document
        - Recent date (within a reasonable timeframe)

        Args:
            contract: The contract with the gap.
            required_doc_type: The type of document needed.
            limit: Maximum number of suggestions.

        Returns:
            List of potential matching documents.
        """
        matches: list[MatchingDocument] = []

        # Get likely contract types for this document type
        likely_types = DOCUMENT_TYPE_TO_CONTRACT_TYPE.get(required_doc_type, [])

        # Get keywords to search for
        keywords = DOCUMENT_TYPE_KEYWORDS.get(required_doc_type, [])

        # Build query for potential matches
        query = (
            select(Contract)
            .where(Contract.tenant_id == self.tenant_id)
            .where(Contract.id != contract.id)
        )

        # Filter by counterparty if known
        if contract.counterparty:
            query = query.where(
                or_(
                    Contract.counterparty == contract.counterparty,
                    Contract.counterparty.ilike(f"%{contract.counterparty}%"),
                )
            )

        # Filter by contract types
        if likely_types:
            query = query.where(Contract.contract_type.in_(likely_types))

        # Order by most recent first
        query = query.order_by(Contract.created_at.desc()).limit(50)

        result = await self.db.execute(query)
        candidates = result.scalars().all()

        # Score candidates
        for candidate in candidates:
            score = 0.0
            reasons = []

            # Check filename/text for keywords
            candidate_text = (
                (candidate.filename or "") +
                " " +
                (candidate.extracted_text or "")[:5000]
            ).lower()

            keyword_matches = sum(1 for kw in keywords if kw in candidate_text)
            if keyword_matches > 0:
                score += min(keyword_matches * 0.2, 0.6)
                reasons.append(f"{keyword_matches} keyword matches")

            # Counterparty match
            if contract.counterparty and candidate.counterparty:
                if candidate.counterparty.lower() == contract.counterparty.lower():
                    score += 0.3
                    reasons.append("Exact counterparty match")
                elif contract.counterparty.lower() in candidate.counterparty.lower():
                    score += 0.15
                    reasons.append("Partial counterparty match")

            # Date proximity (contracts within 1 year of each other)
            if contract.effective_date and candidate.effective_date:
                date_diff = abs((contract.effective_date - candidate.effective_date).days)
                if date_diff < 365:
                    score += 0.1 * (1 - date_diff / 365)
                    reasons.append("Similar timeframe")

            if score > 0.2:
                matches.append(MatchingDocument(
                    contract=candidate,
                    match_score=min(score, 1.0),
                    match_reason="; ".join(reasons),
                ))

        # Sort by score and limit
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches[:limit]

    async def resolve_gap(
        self,
        gap_id: UUID,
        linked_document_id: UUID,
        resolved_by: UUID,
        notes: Optional[str] = None,
    ) -> ComplianceGap:
        """Resolve a compliance gap by linking a document.

        Args:
            gap_id: ID of the gap to resolve.
            linked_document_id: ID of the document that resolves the gap.
            resolved_by: User ID who resolved the gap.
            notes: Optional resolution notes.

        Returns:
            Updated ComplianceGap.
        """
        result = await self.db.execute(
            select(ComplianceGap).where(ComplianceGap.id == gap_id)
        )
        gap = result.scalar_one_or_none()

        if not gap:
            raise ValueError(f"Compliance gap {gap_id} not found")

        gap.linked_document_id = linked_document_id
        gap.status = ComplianceGapStatus.RESOLVED
        gap.resolved_at = datetime.utcnow()
        gap.resolved_by = resolved_by
        gap.resolution_notes = notes

        await self.db.flush()
        logger.info(f"Resolved compliance gap {gap_id} with document {linked_document_id}")

        return gap

    async def waive_gap(
        self,
        gap_id: UUID,
        waiver_reason: str,
        approved_by: UUID,
    ) -> ComplianceGap:
        """Waive a compliance requirement.

        Args:
            gap_id: ID of the gap to waive.
            waiver_reason: Reason for the waiver.
            approved_by: User ID who approved the waiver.

        Returns:
            Updated ComplianceGap.
        """
        result = await self.db.execute(
            select(ComplianceGap).where(ComplianceGap.id == gap_id)
        )
        gap = result.scalar_one_or_none()

        if not gap:
            raise ValueError(f"Compliance gap {gap_id} not found")

        gap.status = ComplianceGapStatus.WAIVED
        gap.waiver_reason = waiver_reason
        gap.waiver_approved_by = approved_by
        gap.waiver_approved_at = datetime.utcnow()

        await self.db.flush()
        logger.info(f"Waived compliance gap {gap_id}: {waiver_reason}")

        return gap

    async def _load_applicable_rules(
        self,
        industry: Industry,
        contract_type: Optional[str],
    ) -> list[IndustryComplianceRule]:
        """Load compliance rules applicable to this industry and contract type."""
        query = (
            select(IndustryComplianceRule)
            .where(IndustryComplianceRule.tenant_id == self.tenant_id)
            .where(IndustryComplianceRule.is_active == True)
            .where(IndustryComplianceRule.industry == industry)
        )

        if contract_type:
            query = query.where(
                IndustryComplianceRule.primary_contract_type == contract_type
            )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_linked_contracts(self, contract: Contract) -> list[Contract]:
        """Get all contracts linked to this contract."""
        # Get child links
        child_query = (
            select(Contract)
            .join(ContractLink, ContractLink.child_contract_id == Contract.id)
            .where(ContractLink.parent_contract_id == contract.id)
        )

        # Get parent links
        parent_query = (
            select(Contract)
            .join(ContractLink, ContractLink.parent_contract_id == Contract.id)
            .where(ContractLink.child_contract_id == contract.id)
        )

        child_result = await self.db.execute(child_query)
        parent_result = await self.db.execute(parent_query)

        linked = list(child_result.scalars().all()) + list(parent_result.scalars().all())
        return linked

    async def _identify_document_types(
        self,
        contracts: list[Contract],
    ) -> set[ComplianceDocumentType]:
        """Identify compliance document types present in a list of contracts."""
        doc_types: set[ComplianceDocumentType] = set()

        for contract in contracts:
            # Check filename and text for document type indicators
            text = (
                (contract.filename or "") +
                " " +
                (contract.extracted_text or "")[:10000]
            ).lower()

            for doc_type, keywords in DOCUMENT_TYPE_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    doc_types.add(doc_type)

        return doc_types

    def _condition_applies(self, contract: Contract, condition: str) -> bool:
        """Check if a rule condition applies to this contract.

        Simple keyword-based check. Can be extended with more sophisticated logic.
        """
        condition_lower = condition.lower()
        contract_text = (
            (contract.filename or "") +
            " " +
            (contract.extracted_text or "")[:10000]
        ).lower()

        # Check for common conditions
        if "phi involved" in condition_lower or "phi" in condition_lower:
            return any(kw in contract_text for kw in ["phi", "protected health information"])

        if "personal data" in condition_lower:
            return any(kw in contract_text for kw in ["personal data", "gdpr", "data subject"])

        if "hazardous" in condition_lower:
            return any(kw in contract_text for kw in ["hazardous", "toxic", "chemical"])

        # Default: assume condition applies
        return True

    def _build_gap_description(self, rule: IndustryComplianceRule) -> str:
        """Build a human-readable description of the compliance gap."""
        doc_type_name = rule.required_document_type.value.replace("_", " ").title()

        description = f"Missing required {doc_type_name}."

        if rule.regulatory_reference:
            description += f" Required by {rule.regulatory_reference}."

        if rule.condition_description:
            description += f" Applies when: {rule.condition_description}."

        return description

    def _calculate_due_date(self, severity: ComplianceGapSeverity) -> date:
        """Calculate resolution due date based on severity."""
        days = SEVERITY_DEADLINES.get(severity, 60)
        return date.today() + timedelta(days=days)


async def check_contract_compliance(
    db: AsyncSession,
    tenant_id: UUID,
    contract: Contract,
    industry: Optional[Industry] = None,
) -> ComplianceCheckResult:
    """Convenience function to check contract compliance.

    Args:
        db: Database session.
        tenant_id: Tenant ID for rule filtering.
        contract: Contract to check.
        industry: Optional industry override.

    Returns:
        ComplianceCheckResult with gaps and score.
    """
    detector = ComplianceGapDetector(db, tenant_id)
    return await detector.check_compliance(contract, industry)
