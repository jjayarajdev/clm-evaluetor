"""Smart document metadata extractor using section-targeted approach."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import openai_client, extract_json_from_response
from app.config import settings
from app.models.contract import Contract

from .models import DocumentCard, PartyInfo, ParentReference
from .prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT

logger = logging.getLogger(__name__)

# Use mini model for extraction (cheaper, sufficient for metadata)
EXTRACTION_MODEL = "gpt-4o-mini"
MAX_CONCURRENT = 5


class SmartDocumentExtractor:
    """Extract rich metadata from contracts using targeted sections."""

    async def extract_batch(
        self,
        db: AsyncSession,
        contract_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, DocumentCard]:
        """Extract DocumentCards for a batch of contracts.

        Returns a dict mapping contract_id -> DocumentCard.
        """
        # Load contracts
        result = await db.execute(
            select(Contract).where(Contract.id.in_(contract_ids))
        )
        contracts = result.scalars().all()

        # Extract in parallel with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        cards: dict[uuid.UUID, DocumentCard] = {}

        async def _extract_one(contract: Contract) -> None:
            async with semaphore:
                try:
                    card = await self._extract_single(contract)
                    cards[contract.id] = card
                except Exception as e:
                    logger.warning(
                        f"Extraction failed for {contract.filename}: {e}"
                    )
                    # Return a minimal card from existing data
                    cards[contract.id] = self._fallback_card(contract)

        await asyncio.gather(*[_extract_one(c) for c in contracts])
        logger.info(f"Extracted {len(cards)} document cards")
        return cards

    async def _extract_single(self, contract: Contract) -> DocumentCard:
        """Extract a DocumentCard from a single contract."""
        full_text = contract.extracted_text or ""
        if not full_text.strip():
            return self._fallback_card(contract)

        targeted_text = self._build_targeted_text(full_text, contract.filename)
        content_hash = hashlib.md5(full_text[:5000].encode()).hexdigest()

        prompt = EXTRACTION_USER_PROMPT.format(
            filename=contract.filename,
            targeted_text=targeted_text,
        )

        response = await openai_client.chat.completions.create(
            model=EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content or ""
        data = extract_json_from_response(raw)
        if not data:
            logger.warning(f"No JSON from extraction for {contract.filename}")
            return self._fallback_card(contract)

        return self._parse_extraction(contract.id, contract.filename, data, content_hash)

    def _build_targeted_text(self, full_text: str, filename: str) -> str:
        """Build focused text for extraction instead of first 10K chars.

        Extracts key sections rather than a blind truncation.
        """
        parts: list[tuple[str, str]] = []

        # 1. Preamble (first 2500 chars) — title, parties, recitals
        parts.append(("PREAMBLE (first 2500 chars)", full_text[:2500]))

        # 2. Table of Contents (if present)
        toc = self._extract_toc(full_text)
        if toc:
            parts.append(("TABLE OF CONTENTS", toc))

        # 3. Sections referencing exhibits/attachments/schedules
        ref_keywords = [
            "Exhibit", "Attachment", "Schedule", "Annex",
            "Appendix", "Statement of Work",
        ]
        ref_sections = set()
        for kw in ref_keywords:
            for section in self._find_paragraphs_containing(full_text, kw):
                if section not in ref_sections and len(section) > 30:
                    ref_sections.add(section)
                    if len(ref_sections) >= 15:
                        break
        if ref_sections:
            combined = "\n".join(list(ref_sections)[:15])
            parts.append(("CROSS-REFERENCE SECTIONS", combined[:3000]))

        # 4. Relationship language sections
        rel_keywords = [
            "pursuant to", "amendment to", "under the terms of",
            "incorporated by reference", "attached hereto",
            "this Agreement", "Master Service",
        ]
        rel_sections = set()
        for kw in rel_keywords:
            for section in self._find_paragraphs_containing(full_text, kw):
                if section not in rel_sections:
                    rel_sections.add(section)
                    if len(rel_sections) >= 6:
                        break
        if rel_sections:
            combined = "\n".join(list(rel_sections)[:6])
            parts.append(("RELATIONSHIP LANGUAGE", combined[:2000]))

        # 5. Signature block / end (last 1000 chars)
        if len(full_text) > 3000:
            parts.append(("SIGNATURE BLOCK (last 1000 chars)", full_text[-1000:]))

        # Assemble with budget
        return self._assemble_with_budget(parts, max_chars=8000)

    def _extract_toc(self, text: str) -> str | None:
        """Extract Table of Contents section if present."""
        # Look for "Table of Contents" header
        toc_patterns = [
            r"(?i)table\s+of\s+contents\s*\n([\s\S]{100,2000}?)(?=\n\s*\n\s*\n|\n[A-Z]{2,}|\n\d+\.\s+[A-Z])",
            r"(?i)contents\s*\n([\s\S]{100,2000}?)(?=\n\s*\n\s*\n)",
        ]
        for pattern in toc_patterns:
            match = re.search(pattern, text[:10000])
            if match:
                return match.group(1).strip()[:1500]
        return None

    def _find_paragraphs_containing(
        self, text: str, keyword: str, context_chars: int = 300
    ) -> list[str]:
        """Find paragraphs containing a keyword with surrounding context."""
        results = []
        # Case-insensitive search
        lower_text = text.lower()
        lower_kw = keyword.lower()
        start = 0
        while True:
            idx = lower_text.find(lower_kw, start)
            if idx == -1:
                break
            # Extract context around the match
            ctx_start = max(0, idx - context_chars)
            ctx_end = min(len(text), idx + len(keyword) + context_chars)
            snippet = text[ctx_start:ctx_end].strip()
            results.append(snippet)
            start = idx + len(keyword)
            if len(results) >= 10:
                break
        return results

    def _assemble_with_budget(
        self, parts: list[tuple[str, str]], max_chars: int
    ) -> str:
        """Assemble labeled sections within a character budget."""
        output = []
        used = 0
        for label, content in parts:
            section = f"=== {label} ===\n{content}\n"
            if used + len(section) > max_chars:
                remaining = max_chars - used
                if remaining > 200:
                    section = section[:remaining] + "\n[truncated]"
                else:
                    break
            output.append(section)
            used += len(section)
        return "\n".join(output)

    def _parse_extraction(
        self,
        contract_id: uuid.UUID,
        filename: str,
        data: dict,
        content_hash: str,
    ) -> DocumentCard:
        """Parse LLM extraction response into a DocumentCard."""
        parties = []
        for p in data.get("parties") or []:
            if isinstance(p, dict) and p.get("name"):
                parties.append(PartyInfo(name=p["name"], role=p.get("role")))

        parent_refs = []
        for pr in data.get("parent_references") or []:
            if isinstance(pr, dict):
                parent_refs.append(ParentReference(
                    referenced_type=pr.get("referenced_type"),
                    referenced_title=pr.get("referenced_title"),
                    relationship=pr.get("relationship"),
                    party_names=pr.get("party_names") or [],
                    referenced_date=pr.get("referenced_date"),
                    reference_text=pr.get("reference_text"),
                ))

        child_refs = data.get("child_references") or []
        if isinstance(child_refs, list):
            child_refs = [str(c) for c in child_refs if c]
        else:
            child_refs = []

        return DocumentCard(
            contract_id=contract_id,
            filename=filename,
            title=data.get("title"),
            doc_type=data.get("doc_type"),
            doc_identifier=data.get("doc_identifier"),
            doc_number=data.get("doc_number"),
            parties=parties,
            parent_references=parent_refs,
            child_references=child_refs,
            subject_summary=data.get("subject_summary"),
            effective_date=data.get("effective_date"),
            term=data.get("term"),
            governing_law=data.get("governing_law"),
            financial_summary=data.get("financial_summary"),
            extraction_confidence=float(data.get("extraction_confidence", 0.5)),
            content_hash=content_hash,
        )

    def _fallback_card(self, contract: Contract) -> DocumentCard:
        """Create a minimal DocumentCard from existing contract data."""
        # Infer doc_type from filename
        fn = contract.filename.lower()
        doc_type = "OTHER"
        doc_identifier = None
        doc_number = None

        if fn.startswith("msa"):
            doc_type = "MSA"
        elif fn.startswith("lsa"):
            doc_type = "LSA"
        elif fn.startswith("exhibit"):
            doc_type = "EXHIBIT"
            m = re.match(r"exhibit\s+([\d.]+)", fn, re.IGNORECASE)
            if m:
                doc_identifier = f"Exhibit {m.group(1)}"
                doc_number = m.group(1)
        elif fn.startswith("attachment"):
            doc_type = "ATTACHMENT"
            m = re.match(r"attachment\s+([\w-]+)", fn, re.IGNORECASE)
            if m:
                doc_identifier = f"Attachment {m.group(1)}"
                doc_number = m.group(1)
        elif fn.startswith("schedule"):
            doc_type = "SCHEDULE"

        parties = []
        if contract.counterparty:
            parties.append(PartyInfo(name=contract.counterparty))

        return DocumentCard(
            contract_id=contract.id,
            filename=contract.filename,
            doc_type=doc_type,
            doc_identifier=doc_identifier,
            doc_number=doc_number,
            parties=parties,
            extraction_confidence=0.2,
        )
