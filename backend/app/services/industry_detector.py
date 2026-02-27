"""Industry Detection Service.

Uses signal-based scoring to detect the industry of a contract based on:
- Terminology and keyword matches
- Regulatory references
- Counterparty industry (if known)
- Document type hints
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.industry import Industry

logger = logging.getLogger(__name__)


# Signal weights for industry detection
SIGNAL_WEIGHTS = {
    "terminology_match": 0.35,
    "regulatory_references": 0.30,
    "counterparty_industry": 0.20,
    "document_type_hints": 0.15,
}


# Industry-specific keywords for terminology matching
INDUSTRY_KEYWORDS: dict[Industry, list[str]] = {
    Industry.PHARMACEUTICAL: [
        "fda", "gmp", "good manufacturing practice", "pharmacovigilance",
        "drug", "clinical trial", "21 cfr", "batch release", "api",
        "active pharmaceutical ingredient", "excipient", "drug product",
        "nda", "anda", "biologics", "pharmaceutical", "drug substance",
        "stability testing", "ich guidelines", "cmc", "quality agreement",
        "batch record", "deviation", "capa", "out of specification",
        "annual product review", "process validation",
    ],
    Industry.HEALTHCARE: [
        "hipaa", "phi", "protected health information", "covered entity",
        "business associate", "patient data", "medical records", "ehr",
        "emr", "electronic health", "healthcare", "health care",
        "patient privacy", "medical device", "clinical", "hospital",
        "physician", "diagnostic", "treatment", "care provider",
        "health insurance", "medicare", "medicaid", "cms",
    ],
    Industry.CHEMICAL: [
        "msds", "sds", "safety data sheet", "hazardous", "cas number",
        "osha", "chemical composition", "formulation", "chemical",
        "toxic", "flammable", "corrosive", "reactive", "epa",
        "environmental protection", "waste disposal", "reach",
        "chemical safety", "hazmat", "material safety",
    ],
    Industry.MANUFACTURING: [
        "iso 9001", "quality management", "production", "supplier",
        "raw materials", "inspection", "specifications", "manufacturing",
        "assembly", "inventory", "supply chain", "warehouse",
        "finished goods", "work in progress", "bill of materials",
        "quality control", "quality assurance", "defect rate",
        "yield", "throughput", "lean manufacturing",
    ],
    Industry.TECHNOLOGY: [
        "saas", "software as a service", "cloud", "data processing",
        "gdpr", "soc 2", "soc2", "uptime", "api", "software",
        "platform", "application", "data center", "cybersecurity",
        "encryption", "data breach", "personal data", "data subject",
        "information security", "it services", "technical support",
        "source code", "intellectual property", "license",
    ],
    Industry.FINANCIAL_SERVICES: [
        "finra", "sec", "securities", "banking", "investment",
        "sox", "sarbanes-oxley", "anti-money laundering", "aml",
        "kyc", "know your customer", "fiduciary", "broker-dealer",
        "asset management", "custodian", "trading", "financial",
        "audit", "compliance", "regulatory", "capital requirements",
        "risk management", "credit", "loan", "mortgage",
    ],
    Industry.ENERGY: [
        "energy", "power", "electricity", "natural gas", "oil",
        "renewable", "solar", "wind", "hydroelectric", "utility",
        "grid", "transmission", "distribution", "generation",
        "ferc", "nerc", "petroleum", "refinery", "pipeline",
        "energy efficiency", "carbon", "emissions",
    ],
    Industry.AEROSPACE_DEFENSE: [
        "defense", "aerospace", "military", "dod", "department of defense",
        "itar", "far", "dfars", "classified", "security clearance",
        "export control", "ear", "government contract", "prime contractor",
        "subcontractor", "compliance", "as9100", "nadcap",
        "aircraft", "satellite", "missile", "weapon system",
    ],
    Industry.FOOD_BEVERAGE: [
        "food safety", "haccp", "fsma", "fda", "usda", "organic",
        "food grade", "gmp", "allergen", "nutrition", "labeling",
        "food processing", "beverage", "ingredient", "additive",
        "shelf life", "cold chain", "sanitation", "food contact",
    ],
    Industry.AUTOMOTIVE: [
        "automotive", "vehicle", "oem", "tier 1", "tier 2",
        "iatf 16949", "ppap", "apqp", "fmea", "spc",
        "parts", "components", "assembly", "recall", "warranty",
        "emissions", "safety standards", "crash test",
    ],
    Industry.TELECOMMUNICATIONS: [
        "telecommunications", "telecom", "fcc", "spectrum",
        "wireless", "cellular", "broadband", "fiber", "network",
        "carrier", "roaming", "interconnection", "voip",
        "data transmission", "bandwidth", "latency",
    ],
    Industry.RETAIL: [
        "retail", "merchandise", "point of sale", "pos",
        "inventory", "store", "ecommerce", "e-commerce",
        "consumer", "product", "brand", "distribution",
        "fulfillment", "returns", "customer service",
    ],
    Industry.CONSTRUCTION: [
        "construction", "building", "contractor", "subcontractor",
        "architect", "engineer", "permit", "code", "safety",
        "osha", "jobsite", "project", "renovation", "demolition",
        "materials", "equipment", "inspection",
    ],
    Industry.PROFESSIONAL_SERVICES: [
        "consulting", "advisory", "professional services",
        "engagement", "deliverable", "milestone", "fee",
        "hourly rate", "retainer", "statement of work",
        "scope", "change order", "acceptance criteria",
    ],
}


# Regulatory references that indicate specific industries
REGULATORY_REFERENCES: dict[Industry, list[str]] = {
    Industry.PHARMACEUTICAL: [
        r"21\s*cfr\s*part\s*\d+",
        r"ich\s+[qseqm]\d+",
        r"fda\s+guidance",
        r"usp\s+chapter",
        r"pharmacopeia",
        r"gmp\s+compliance",
        r"annex\s+\d+",  # EU GMP Annexes
    ],
    Industry.HEALTHCARE: [
        r"hipaa",
        r"45\s*cfr\s*part\s*\d+",
        r"hitech\s+act",
        r"omnibus\s+rule",
        r"phi\s+protection",
        r"covered\s+entity",
        r"business\s+associate\s+agreement",
    ],
    Industry.TECHNOLOGY: [
        r"gdpr\s+article",
        r"soc\s*2\s*type",
        r"iso\s*27001",
        r"ccpa",
        r"data\s+protection\s+act",
        r"standard\s+contractual\s+clauses",
    ],
    Industry.CHEMICAL: [
        r"reach\s+regulation",
        r"29\s*cfr\s*1910",
        r"osha\s+standard",
        r"epa\s+regulation",
        r"tsca",
        r"rcra",
    ],
    Industry.FINANCIAL_SERVICES: [
        r"reg\s+[a-z]",  # Reg D, Reg S, etc.
        r"finra\s+rule",
        r"sec\s+rule",
        r"sox\s+section",
        r"dodd[\s-]*frank",
        r"mifid",
        r"basel\s+iii",
    ],
    Industry.AEROSPACE_DEFENSE: [
        r"itar\s+\d+",
        r"dfars\s+\d+",
        r"far\s+\d+\.\d+",
        r"nist\s+sp\s+800",
        r"cmmc\s+level",
        r"cjis",
    ],
}


@dataclass
class IndustrySignal:
    """A signal contributing to industry detection."""
    industry: Industry
    signal_type: str
    match: str
    weight: float
    score: float


@dataclass
class IndustryDetectionResult:
    """Result of industry detection."""
    industry: Industry
    confidence: float
    alternative_industries: list[tuple[Industry, float]] = field(default_factory=list)
    signals: list[IndustrySignal] = field(default_factory=list)
    reasoning: str = ""

    @property
    def is_confident(self) -> bool:
        """Check if detection confidence is high enough."""
        return self.confidence >= 0.6

    @property
    def needs_review(self) -> bool:
        """Check if this detection should be reviewed by a human."""
        # Low confidence or close alternatives
        if self.confidence < 0.4:
            return True
        if self.alternative_industries and self.alternative_industries[0][1] > self.confidence * 0.8:
            return True
        return False


class IndustryDetector:
    """Service for detecting contract industry using signal-based scoring."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_industry(
        self,
        contract: Contract,
        counterparty_industry: Optional[Industry] = None,
    ) -> IndustryDetectionResult:
        """Detect the industry of a contract.

        Args:
            contract: The contract to analyze.
            counterparty_industry: Known industry of the counterparty (if available).

        Returns:
            IndustryDetectionResult with detected industry and confidence.
        """
        signals: list[IndustrySignal] = []
        industry_scores: dict[Industry, float] = {ind: 0.0 for ind in Industry}

        # Get text to analyze
        text = self._get_analyzable_text(contract)
        text_lower = text.lower()

        # 1. Terminology matching
        terminology_signals = self._analyze_terminology(text_lower)
        signals.extend(terminology_signals)
        for signal in terminology_signals:
            industry_scores[signal.industry] += signal.score

        # 2. Regulatory references
        regulatory_signals = self._analyze_regulatory_references(text_lower)
        signals.extend(regulatory_signals)
        for signal in regulatory_signals:
            industry_scores[signal.industry] += signal.score

        # 3. Counterparty industry hint
        if counterparty_industry:
            cp_signal = IndustrySignal(
                industry=counterparty_industry,
                signal_type="counterparty_industry",
                match="Known counterparty industry",
                weight=SIGNAL_WEIGHTS["counterparty_industry"],
                score=SIGNAL_WEIGHTS["counterparty_industry"],
            )
            signals.append(cp_signal)
            industry_scores[counterparty_industry] += cp_signal.score

        # 4. Document type hints
        doc_signals = self._analyze_document_type(contract)
        signals.extend(doc_signals)
        for signal in doc_signals:
            industry_scores[signal.industry] += signal.score

        # Find the top industry
        sorted_industries = sorted(
            industry_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Calculate confidence (normalize scores)
        max_score = sorted_industries[0][1] if sorted_industries[0][1] > 0 else 0
        total_score = sum(s for _, s in sorted_industries if s > 0)

        if total_score == 0:
            # No signals found, default to OTHER with low confidence
            return IndustryDetectionResult(
                industry=Industry.OTHER,
                confidence=0.1,
                signals=signals,
                reasoning="No industry-specific signals detected.",
            )

        # Top industry
        top_industry = sorted_industries[0][0]
        confidence = max_score / total_score if total_score > 0 else 0

        # Alternatives (industries with significant scores)
        alternatives = [
            (ind, score / total_score)
            for ind, score in sorted_industries[1:5]
            if score > 0 and score >= max_score * 0.3
        ]

        # Build reasoning
        top_signals = sorted(signals, key=lambda s: s.score, reverse=True)[:5]
        reasoning_parts = [f"Industry detected as {top_industry.value}."]
        if top_signals:
            reasoning_parts.append("Key signals:")
            for sig in top_signals:
                reasoning_parts.append(f"  - {sig.signal_type}: '{sig.match}'")

        return IndustryDetectionResult(
            industry=top_industry,
            confidence=min(confidence, 1.0),
            alternative_industries=alternatives,
            signals=signals,
            reasoning=" ".join(reasoning_parts),
        )

    def _get_analyzable_text(self, contract: Contract) -> str:
        """Get text from contract for analysis."""
        parts = []

        # Use extracted text if available
        if contract.extracted_text:
            parts.append(contract.extracted_text)

        # Also include filename and counterparty
        if contract.filename:
            parts.append(contract.filename)
        if contract.counterparty:
            parts.append(contract.counterparty)

        return " ".join(parts)

    def _analyze_terminology(self, text: str) -> list[IndustrySignal]:
        """Analyze text for industry-specific terminology."""
        signals = []
        weight = SIGNAL_WEIGHTS["terminology_match"]

        for industry, keywords in INDUSTRY_KEYWORDS.items():
            matches = []
            for keyword in keywords:
                # Count occurrences (case-insensitive)
                count = text.count(keyword.lower())
                if count > 0:
                    matches.append((keyword, count))

            if matches:
                # Score based on number of unique keywords and total occurrences
                unique_keywords = len(matches)
                total_occurrences = sum(c for _, c in matches)

                # Normalize score (log scale for occurrences to prevent domination)
                import math
                base_score = unique_keywords * 0.1
                occurrence_bonus = math.log1p(total_occurrences) * 0.05
                score = min((base_score + occurrence_bonus) * weight, weight)

                # Create signal for top 3 matches
                top_matches = sorted(matches, key=lambda x: x[1], reverse=True)[:3]
                match_str = ", ".join(f"{kw}({cnt})" for kw, cnt in top_matches)

                signals.append(IndustrySignal(
                    industry=industry,
                    signal_type="terminology_match",
                    match=match_str,
                    weight=weight,
                    score=score,
                ))

        return signals

    def _analyze_regulatory_references(self, text: str) -> list[IndustrySignal]:
        """Analyze text for regulatory references."""
        signals = []
        weight = SIGNAL_WEIGHTS["regulatory_references"]

        for industry, patterns in REGULATORY_REFERENCES.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, text, re.IGNORECASE)
                matches.extend(found)

            if matches:
                # Unique matches
                unique_matches = list(set(matches))

                # Score based on number of unique regulatory references
                score = min(len(unique_matches) * 0.15 * weight, weight)

                signals.append(IndustrySignal(
                    industry=industry,
                    signal_type="regulatory_references",
                    match=", ".join(unique_matches[:3]),
                    weight=weight,
                    score=score,
                ))

        return signals

    def _analyze_document_type(self, contract: Contract) -> list[IndustrySignal]:
        """Analyze document type for industry hints."""
        signals = []
        weight = SIGNAL_WEIGHTS["document_type_hints"]

        # Check filename for hints
        filename_lower = (contract.filename or "").lower()

        # Quality Agreement typically pharmaceutical
        if "quality agreement" in filename_lower or "qa_" in filename_lower:
            signals.append(IndustrySignal(
                industry=Industry.PHARMACEUTICAL,
                signal_type="document_type_hints",
                match="Quality Agreement in filename",
                weight=weight,
                score=weight * 0.8,
            ))

        # BAA typically healthcare
        if "baa" in filename_lower or "business associate" in filename_lower:
            signals.append(IndustrySignal(
                industry=Industry.HEALTHCARE,
                signal_type="document_type_hints",
                match="BAA in filename",
                weight=weight,
                score=weight * 0.9,
            ))

        # DPA typically technology
        if "dpa" in filename_lower or "data processing" in filename_lower:
            signals.append(IndustrySignal(
                industry=Industry.TECHNOLOGY,
                signal_type="document_type_hints",
                match="DPA in filename",
                weight=weight,
                score=weight * 0.7,
            ))

        # SaaS typically technology
        if "saas" in filename_lower or "cloud" in filename_lower:
            signals.append(IndustrySignal(
                industry=Industry.TECHNOLOGY,
                signal_type="document_type_hints",
                match="SaaS/Cloud in filename",
                weight=weight,
                score=weight * 0.8,
            ))

        return signals


async def detect_contract_industry(
    db: AsyncSession,
    contract: Contract,
    counterparty_industry: Optional[Industry] = None,
) -> IndustryDetectionResult:
    """Convenience function to detect contract industry.

    Args:
        db: Database session.
        contract: Contract to analyze.
        counterparty_industry: Known industry of counterparty.

    Returns:
        IndustryDetectionResult with detected industry.
    """
    detector = IndustryDetector(db)
    return await detector.detect_industry(contract, counterparty_industry)
