"""Semantic chunking service for contract documents."""

import re
from dataclasses import dataclass, field
from typing import Iterator

from app.services.parser import PageContent, ParsedDocument


# Target chunk sizes (in tokens, roughly 4 chars per token)
TARGET_CHUNK_SIZE = 500  # tokens
MAX_CHUNK_SIZE = 1500  # tokens
OVERLAP_SIZE = 100  # tokens

# Approximate chars per token for estimation
CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    """A semantic chunk from a document."""

    text: str
    chunk_index: int
    section_number: str | None = None
    section_title: str | None = None
    page_start: int = 1
    page_end: int = 1
    char_start: int = 0
    char_end: int = 0
    token_count: int = 0

    def __post_init__(self) -> None:
        # Estimate token count
        self.token_count = len(self.text) // CHARS_PER_TOKEN


@dataclass
class ChunkedDocument:
    """Result of chunking a document."""

    filename: str
    chunks: list[Chunk] = field(default_factory=list)
    total_chunks: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        self.total_chunks = len(self.chunks)
        self.total_tokens = sum(c.token_count for c in self.chunks)


# Patterns for detecting section headers
SECTION_PATTERNS = [
    # Article I, Article 1, ARTICLE ONE
    re.compile(r"^(?:ARTICLE|Article)\s+([IVXLC\d]+|[A-Z]+)[\.:]\s*(.*)$", re.MULTILINE),
    # Section 1, SECTION 1.1, Section A
    re.compile(r"^(?:SECTION|Section)\s+(\d+(?:\.\d+)*|[A-Z])[\.:]\s*(.*)$", re.MULTILINE),
    # 1. Title, 1.1 Title, 1.1.1 Title
    re.compile(r"^(\d+(?:\.\d+)*)[\.\)]\s+([A-Z][^.\n]{2,50})$", re.MULTILINE),
    # (a) Title, (1) Title, (i) Title
    re.compile(r"^\(([a-z]|\d+|[ivx]+)\)\s+([A-Z][^.\n]{2,50})$", re.MULTILINE),
    # UPPERCASE HEADERS (all caps, 3-50 chars)
    re.compile(r"^([A-Z][A-Z\s]{2,49})$", re.MULTILINE),
]

# Patterns for clause boundaries
CLAUSE_BOUNDARY_PATTERNS = [
    # Whereas clauses
    re.compile(r"\bWHEREAS[,:]", re.IGNORECASE),
    # Now therefore
    re.compile(r"\bNOW,?\s+THEREFORE", re.IGNORECASE),
    # Defined terms (capitalized in quotes)
    re.compile(r'"[A-Z][^"]+"\s+(?:means|shall mean|refers to)', re.IGNORECASE),
    # Common clause starters
    re.compile(
        r"^(?:The\s+(?:Company|Contractor|Vendor|Party|Client)|"
        r"Each\s+party|Neither\s+party|Both\s+parties|"
        r"Upon|In\s+the\s+event|Notwithstanding|Subject\s+to|"
        r"Except\s+as|Unless\s+otherwise|For\s+purposes\s+of)",
        re.MULTILINE | re.IGNORECASE,
    ),
]


class DocumentChunker:
    """Service for semantically chunking documents."""

    def __init__(
        self,
        target_size: int = TARGET_CHUNK_SIZE,
        max_size: int = MAX_CHUNK_SIZE,
        overlap: int = OVERLAP_SIZE,
    ) -> None:
        """Initialize chunker with size parameters.

        Args:
            target_size: Target chunk size in tokens.
            max_size: Maximum chunk size in tokens.
            overlap: Overlap between chunks in tokens.
        """
        self.target_size = target_size
        self.max_size = max_size
        self.overlap = overlap

    def chunk_document(self, doc: ParsedDocument) -> ChunkedDocument:
        """Chunk a parsed document into semantic segments.

        Args:
            doc: ParsedDocument from the parser.

        Returns:
            ChunkedDocument with list of chunks.
        """
        if not doc.success or not doc.full_text:
            return ChunkedDocument(filename=doc.filename)

        # First try to detect sections
        sections = self._detect_sections(doc.full_text)

        if sections:
            # Chunk by sections
            chunks = list(self._chunk_by_sections(sections, doc))
        else:
            # Fall back to paragraph-based chunking
            chunks = list(self._chunk_by_paragraphs(doc))

        # Ensure chunks aren't too large - recursively split if needed
        final_chunks = []
        for chunk in chunks:
            if chunk.token_count > self.max_size:
                # Split large chunks
                sub_chunks = list(self._split_large_chunk(chunk, len(final_chunks)))
                final_chunks.extend(sub_chunks)
            else:
                chunk.chunk_index = len(final_chunks)
                final_chunks.append(chunk)

        return ChunkedDocument(
            filename=doc.filename,
            chunks=final_chunks,
        )

    def _detect_sections(self, text: str) -> list[tuple[str, str, int, str]]:
        """Detect section headers in text.

        Args:
            text: Full document text.

        Returns:
            List of (section_number, section_title, position, full_match).
        """
        sections = []

        for pattern in SECTION_PATTERNS:
            for match in pattern.finditer(text):
                groups = match.groups()
                if len(groups) >= 2:
                    section_num = groups[0].strip() if groups[0] else ""
                    section_title = groups[1].strip() if len(groups) > 1 and groups[1] else ""
                else:
                    section_num = ""
                    section_title = groups[0].strip() if groups else ""

                sections.append(
                    (section_num, section_title, match.start(), match.group(0))
                )

        # Sort by position and remove duplicates (overlapping matches)
        sections.sort(key=lambda x: x[2])

        # Remove overlapping matches
        filtered = []
        last_end = -1
        for sec in sections:
            if sec[2] > last_end:
                filtered.append(sec)
                last_end = sec[2] + len(sec[3])

        return filtered

    def _chunk_by_sections(
        self, sections: list[tuple[str, str, int, str]], doc: ParsedDocument
    ) -> Iterator[Chunk]:
        """Chunk document based on detected sections.

        Args:
            sections: List of detected sections.
            doc: Parsed document.

        Yields:
            Chunk objects.
        """
        text = doc.full_text
        chunk_index = 0

        for i, (section_num, section_title, start, _) in enumerate(sections):
            # Find end of this section (start of next section or end of text)
            if i + 1 < len(sections):
                end = sections[i + 1][2]
            else:
                end = len(text)

            section_text = text[start:end].strip()
            if not section_text:
                continue

            # Determine page numbers for this section
            page_start, page_end = self._find_page_range(doc.pages, start, end)

            yield Chunk(
                text=section_text,
                chunk_index=chunk_index,
                section_number=section_num or None,
                section_title=section_title or None,
                page_start=page_start,
                page_end=page_end,
                char_start=start,
                char_end=end,
            )
            chunk_index += 1

        # Handle any text before the first section
        if sections and sections[0][2] > 0:
            preamble = text[: sections[0][2]].strip()
            if preamble and len(preamble) > 50:  # Only if substantial
                page_start, page_end = self._find_page_range(doc.pages, 0, sections[0][2])
                yield Chunk(
                    text=preamble,
                    chunk_index=0,  # Will be reindexed
                    section_number=None,
                    section_title="Preamble",
                    page_start=page_start,
                    page_end=page_end,
                    char_start=0,
                    char_end=sections[0][2],
                )

    def _chunk_by_paragraphs(self, doc: ParsedDocument) -> Iterator[Chunk]:
        """Chunk document by paragraphs when no sections are detected.

        Args:
            doc: Parsed document.

        Yields:
            Chunk objects.
        """
        text = doc.full_text
        paragraphs = text.split("\n\n")

        current_chunk: list[str] = []
        current_tokens = 0
        chunk_index = 0
        char_start = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_tokens = len(para) // CHARS_PER_TOKEN

            # If adding this paragraph exceeds target, emit current chunk
            if current_tokens + para_tokens > self.target_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                char_end = char_start + len(chunk_text)
                page_start, page_end = self._find_page_range(doc.pages, char_start, char_end)

                yield Chunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    char_start=char_start,
                    char_end=char_end,
                )

                chunk_index += 1

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                if overlap_text:
                    current_chunk = [overlap_text]
                    current_tokens = len(overlap_text) // CHARS_PER_TOKEN
                else:
                    current_chunk = []
                    current_tokens = 0
                char_start = char_end - len(overlap_text) if overlap_text else char_end

            current_chunk.append(para)
            current_tokens += para_tokens

        # Emit final chunk
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            char_end = char_start + len(chunk_text)
            page_start, page_end = self._find_page_range(doc.pages, char_start, char_end)

            yield Chunk(
                text=chunk_text,
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
                char_start=char_start,
                char_end=char_end,
            )

    def _split_large_chunk(self, chunk: Chunk, base_index: int) -> Iterator[Chunk]:
        """Split a large chunk into smaller pieces.

        Args:
            chunk: The chunk to split.
            base_index: Starting index for sub-chunks.

        Yields:
            Smaller Chunk objects.
        """
        text = chunk.text
        target_chars = self.target_size * CHARS_PER_TOKEN
        overlap_chars = self.overlap * CHARS_PER_TOKEN

        start = 0
        sub_index = 0

        while start < len(text):
            end = start + target_chars

            if end >= len(text):
                # Last piece
                sub_text = text[start:]
            else:
                # Find a good break point (paragraph, sentence, or word boundary)
                break_point = self._find_break_point(text, end)
                sub_text = text[start:break_point]
                end = break_point

            if sub_text.strip():
                yield Chunk(
                    text=sub_text.strip(),
                    chunk_index=base_index + sub_index,
                    section_number=chunk.section_number,
                    section_title=f"{chunk.section_title} (part {sub_index + 1})" if chunk.section_title else None,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    char_start=chunk.char_start + start,
                    char_end=chunk.char_start + end,
                )
                sub_index += 1

            # Move start with overlap
            start = max(start + 1, end - overlap_chars)

    def _find_break_point(self, text: str, target: int) -> int:
        """Find a good break point near the target position.

        Args:
            text: Text to search in.
            target: Target position.

        Returns:
            Best break position.
        """
        # Look for paragraph break
        para_break = text.rfind("\n\n", target - 200, target + 200)
        if para_break != -1:
            return para_break + 2

        # Look for sentence break
        for end_char in [".", "!", "?"]:
            sent_break = text.rfind(end_char + " ", target - 100, target + 100)
            if sent_break != -1:
                return sent_break + 2

        # Look for word boundary
        space = text.rfind(" ", target - 50, target + 50)
        if space != -1:
            return space + 1

        # Fall back to target
        return min(target, len(text))

    def _find_page_range(
        self, pages: list[PageContent], char_start: int, char_end: int
    ) -> tuple[int, int]:
        """Find page range for a character range.

        Args:
            pages: List of page contents.
            char_start: Start character position.
            char_end: End character position.

        Returns:
            Tuple of (start_page, end_page).
        """
        if not pages:
            return (1, 1)

        # Build cumulative character counts
        cumulative = 0
        page_boundaries = []
        for page in pages:
            page_boundaries.append((page.page_number, cumulative, cumulative + page.char_count))
            cumulative += page.char_count + 2  # Account for page separators

        start_page = 1
        end_page = 1

        for page_num, page_start, page_end in page_boundaries:
            if page_start <= char_start < page_end:
                start_page = page_num
            if page_start < char_end <= page_end:
                end_page = page_num

        return (start_page, max(start_page, end_page))

    def _get_overlap_text(self, paragraphs: list[str]) -> str:
        """Get overlap text from the end of paragraph list.

        Args:
            paragraphs: List of paragraphs.

        Returns:
            Text to use as overlap.
        """
        if not paragraphs:
            return ""

        overlap_chars = self.overlap * CHARS_PER_TOKEN
        result = []
        total = 0

        for para in reversed(paragraphs):
            if total + len(para) <= overlap_chars:
                result.insert(0, para)
                total += len(para)
            else:
                # Partial paragraph
                remaining = overlap_chars - total
                if remaining > 50:  # Only if substantial
                    result.insert(0, para[-remaining:])
                break

        return "\n\n".join(result)


# Singleton instance
_chunker: DocumentChunker | None = None


def get_chunker() -> DocumentChunker:
    """Get the document chunker singleton."""
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker
