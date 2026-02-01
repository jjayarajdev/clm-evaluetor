"""Document parsing service for extracting text from PDFs and DOCX files."""

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

import fitz  # PyMuPDF
from docx import Document
from docx.opc.exceptions import PackageNotFoundError

logger = logging.getLogger(__name__)


# Minimum characters per page to consider it has valid text (not scanned)
MIN_TEXT_THRESHOLD = 50


@dataclass
class PageContent:
    """Content from a single page."""

    page_number: int
    text: str
    char_count: int = 0

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


@dataclass
class DocumentMetadata:
    """Metadata extracted from the document."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    creator: str | None = None
    creation_date: str | None = None
    modification_date: str | None = None
    page_count: int = 0
    word_count: int = 0


@dataclass
class ParsedDocument:
    """Result of parsing a document."""

    filename: str
    file_type: str  # "pdf" or "docx"
    pages: list[PageContent] = field(default_factory=list)
    full_text: str = ""
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    ocr_used: bool = False
    success: bool = True
    error: str | None = None

    @property
    def page_count(self) -> int:
        """Get total page count."""
        return len(self.pages)

    @property
    def total_chars(self) -> int:
        """Get total character count."""
        return sum(p.char_count for p in self.pages)


class ParserError(Exception):
    """Exception raised for parsing errors."""

    pass


class DocumentParser:
    """Service for parsing PDF and DOCX documents."""

    def __init__(self, enable_ocr: bool = True) -> None:
        """Initialize parser.

        Args:
            enable_ocr: Whether to use OCR for scanned PDFs.
        """
        self.enable_ocr = enable_ocr
        self._tesseract_available: bool | None = None

    def check_tesseract(self) -> bool:
        """Check if Tesseract is available."""
        if self._tesseract_available is not None:
            return self._tesseract_available

        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self._tesseract_available = True
        except Exception:
            logger.warning("Tesseract not available - OCR will be disabled")
            self._tesseract_available = False

        return self._tesseract_available

    def parse_file(self, file_path: str | Path) -> ParsedDocument:
        """Parse a document from a file path.

        Args:
            file_path: Path to the document.

        Returns:
            ParsedDocument with extracted content.
        """
        path = Path(file_path)
        if not path.exists():
            return ParsedDocument(
                filename=path.name,
                file_type="unknown",
                success=False,
                error=f"File not found: {file_path}",
            )

        ext = path.suffix.lower()

        with open(path, "rb") as f:
            if ext == ".pdf":
                return self.parse_pdf(f, path.name)
            elif ext == ".docx":
                return self.parse_docx(f, path.name)
            else:
                return ParsedDocument(
                    filename=path.name,
                    file_type=ext,
                    success=False,
                    error=f"Unsupported file type: {ext}",
                )

    def parse_pdf(self, file: BinaryIO, filename: str = "document.pdf") -> ParsedDocument:
        """Parse a PDF document.

        Args:
            file: File-like object containing PDF data.
            filename: Original filename for reference.

        Returns:
            ParsedDocument with extracted content.
        """
        try:
            # Read the entire content
            content = file.read()
            doc = fitz.open(stream=content, filetype="pdf")

            pages: list[PageContent] = []
            all_text_parts: list[str] = []
            needs_ocr = False

            # Extract text from each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")

                # Clean up text
                text = text.strip()

                # Check if page needs OCR (minimal text extracted)
                if len(text) < MIN_TEXT_THRESHOLD:
                    needs_ocr = True

                pages.append(
                    PageContent(
                        page_number=page_num + 1,
                        text=text,
                    )
                )
                if text:
                    all_text_parts.append(f"[Page {page_num + 1}]\n{text}")

            # Try OCR if needed and available
            ocr_used = False
            if needs_ocr and self.enable_ocr and self.check_tesseract():
                logger.info(f"Attempting OCR for {filename}")
                ocr_pages = self._ocr_pdf(doc)
                if ocr_pages:
                    # Merge OCR results with existing pages
                    pages = self._merge_ocr_results(pages, ocr_pages)
                    all_text_parts = [
                        f"[Page {p.page_number}]\n{p.text}" for p in pages if p.text
                    ]
                    ocr_used = True

            # Extract metadata
            metadata = self._extract_pdf_metadata(doc)
            doc.close()

            # Combine all text
            full_text = "\n\n".join(all_text_parts)
            metadata.word_count = len(full_text.split())

            return ParsedDocument(
                filename=filename,
                file_type="pdf",
                pages=pages,
                full_text=full_text,
                metadata=metadata,
                ocr_used=ocr_used,
                success=True,
            )

        except Exception as e:
            logger.exception(f"Error parsing PDF {filename}")
            return ParsedDocument(
                filename=filename,
                file_type="pdf",
                success=False,
                error=str(e),
            )

    def parse_docx(self, file: BinaryIO, filename: str = "document.docx") -> ParsedDocument:
        """Parse a DOCX document.

        Args:
            file: File-like object containing DOCX data.
            filename: Original filename for reference.

        Returns:
            ParsedDocument with extracted content.
        """
        try:
            doc = Document(file)

            # Extract paragraphs with structure preservation
            paragraphs: list[str] = []
            current_page = 1
            page_contents: dict[int, list[str]] = {1: []}

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                # Detect heading styles
                style_name = para.style.name if para.style else ""
                if style_name.startswith("Heading"):
                    # Add heading marker
                    level = style_name.replace("Heading ", "").replace("Heading", "1")
                    try:
                        level_num = int(level)
                    except ValueError:
                        level_num = 1
                    prefix = "#" * level_num + " "
                    text = f"\n{prefix}{text}\n"

                paragraphs.append(text)

                # DOCX doesn't have page numbers in the same way as PDF
                # We'll estimate pages based on character count (approx 3000 chars/page)
                total_chars = sum(len(p) for p in page_contents[current_page])
                if total_chars > 3000:
                    current_page += 1
                    page_contents[current_page] = []
                page_contents[current_page].append(text)

            # Build pages
            pages = []
            for page_num in sorted(page_contents.keys()):
                page_text = "\n".join(page_contents[page_num])
                if page_text.strip():
                    pages.append(
                        PageContent(
                            page_number=page_num,
                            text=page_text,
                        )
                    )

            # Extract tables
            table_texts = []
            for table in doc.tables:
                table_text = self._extract_table_text(table)
                if table_text:
                    table_texts.append(table_text)

            # Combine all content
            full_text = "\n\n".join(paragraphs)
            if table_texts:
                full_text += "\n\n[Tables]\n" + "\n\n".join(table_texts)

            # Extract metadata from document properties
            metadata = self._extract_docx_metadata(doc)
            metadata.page_count = len(pages)
            metadata.word_count = len(full_text.split())

            return ParsedDocument(
                filename=filename,
                file_type="docx",
                pages=pages,
                full_text=full_text,
                metadata=metadata,
                ocr_used=False,
                success=True,
            )

        except PackageNotFoundError:
            return ParsedDocument(
                filename=filename,
                file_type="docx",
                success=False,
                error="Invalid or corrupted DOCX file",
            )
        except Exception as e:
            logger.exception(f"Error parsing DOCX {filename}")
            return ParsedDocument(
                filename=filename,
                file_type="docx",
                success=False,
                error=str(e),
            )

    def _extract_pdf_metadata(self, doc: fitz.Document) -> DocumentMetadata:
        """Extract metadata from PDF document."""
        meta = doc.metadata or {}

        return DocumentMetadata(
            title=meta.get("title") or None,
            author=meta.get("author") or None,
            subject=meta.get("subject") or None,
            creator=meta.get("creator") or None,
            creation_date=meta.get("creationDate") or None,
            modification_date=meta.get("modDate") or None,
            page_count=len(doc),
        )

    def _extract_docx_metadata(self, doc: Document) -> DocumentMetadata:
        """Extract metadata from DOCX document."""
        props = doc.core_properties

        creation_date = None
        modification_date = None

        if props.created:
            creation_date = props.created.isoformat()
        if props.modified:
            modification_date = props.modified.isoformat()

        return DocumentMetadata(
            title=props.title or None,
            author=props.author or None,
            subject=props.subject or None,
            creator=props.author or None,  # DOCX uses author for creator
            creation_date=creation_date,
            modification_date=modification_date,
        )

    def _extract_table_text(self, table) -> str:
        """Extract text from a DOCX table."""
        rows = []
        for row in table.rows:
            cells = []
            for cell in row.cells:
                cells.append(cell.text.strip())
            rows.append(" | ".join(cells))
        return "\n".join(rows)

    def _ocr_pdf(self, doc: fitz.Document) -> list[PageContent]:
        """Perform OCR on PDF pages using Tesseract.

        Args:
            doc: PyMuPDF document object.

        Returns:
            List of PageContent with OCR text.
        """
        import pytesseract
        from PIL import Image

        pages = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Render page to image at 300 DPI for better OCR
            mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Run OCR
            try:
                text = pytesseract.image_to_string(img, lang="eng")
                text = text.strip()
            except Exception as e:
                logger.warning(f"OCR failed for page {page_num + 1}: {e}")
                text = ""

            pages.append(
                PageContent(
                    page_number=page_num + 1,
                    text=text,
                )
            )

        return pages

    def _merge_ocr_results(
        self, original: list[PageContent], ocr: list[PageContent]
    ) -> list[PageContent]:
        """Merge OCR results with original text extraction.

        Uses OCR text only if it has more content than original.

        Args:
            original: Original text extraction results.
            ocr: OCR extraction results.

        Returns:
            Merged list of PageContent.
        """
        merged = []

        for orig, ocr_page in zip(original, ocr):
            # Use whichever has more text
            if ocr_page.char_count > orig.char_count:
                merged.append(ocr_page)
            else:
                merged.append(orig)

        return merged


# Singleton instance
_parser: DocumentParser | None = None


def get_parser() -> DocumentParser:
    """Get the document parser singleton."""
    global _parser
    if _parser is None:
        _parser = DocumentParser()
    return _parser
