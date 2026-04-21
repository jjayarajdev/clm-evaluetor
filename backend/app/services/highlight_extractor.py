"""Extract pixel-perfect highlight coordinates for clause text in PDFs.

Uses PyMuPDF's search_for() to find exact bounding rectangles for each
clause's text, returning coordinates in PDF points (72 DPI).
"""

import logging
import subprocess
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)


def extract_highlight_rects(
    file_path: str,
    clauses: list[dict],
) -> dict[str, list[dict]]:
    """Extract highlight rectangles for clauses from a PDF.

    Args:
        file_path: Path to PDF (or DOCX — will be converted).
        clauses: List of {"id", "text", "page_number"} dicts.

    Returns:
        Mapping of clause_id → list of {"page", "x0", "y0", "x1", "y1"}.
    """
    pdf_path = _ensure_pdf(file_path)
    if not pdf_path:
        return {}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.warning(f"Cannot open PDF for highlight extraction: {e}")
        return {}

    results: dict[str, list[dict]] = {}

    for clause in clauses:
        clause_id = clause["id"]
        text = clause.get("text", "")
        target_page = clause.get("page_number")

        if not text or len(text) < 10:
            continue

        rects = _search_clause(doc, text, target_page)
        if rects:
            results[clause_id] = rects

    doc.close()

    logger.info(f"Highlight rects: found for {len(results)}/{len(clauses)} clauses")
    return results


def extract_page_dimensions(file_path: str) -> dict[str, dict]:
    """Extract page dimensions (width, height in PDF points) for each page.

    Returns:
        {"1": {"width": 612.0, "height": 792.0}, ...}
    """
    pdf_path = _ensure_pdf(file_path)
    if not pdf_path:
        return {}

    try:
        doc = fitz.open(pdf_path)
        dims = {}
        for i in range(len(doc)):
            page = doc[i]
            dims[str(i + 1)] = {
                "width": round(page.rect.width, 2),
                "height": round(page.rect.height, 2),
            }
        doc.close()
        return dims
    except Exception as e:
        logger.warning(f"Cannot extract page dimensions: {e}")
        return {}


def _ensure_pdf(file_path: str) -> str | None:
    """Ensure we have a PDF to work with. Convert DOCX if needed."""
    if not file_path:
        return None

    path = Path(file_path)
    if not path.exists():
        return None

    lower = path.suffix.lower()
    if lower == ".pdf":
        return file_path

    if lower in (".docx", ".doc"):
        cached_pdf = path.with_suffix(".pdf")
        if cached_pdf.exists():
            return str(cached_pdf)

        # Convert via LibreOffice
        try:
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf",
                 "--outdir", str(path.parent), str(path)],
                check=True, timeout=120, capture_output=True,
            )
            if cached_pdf.exists():
                return str(cached_pdf)
        except Exception as e:
            logger.warning(f"DOCX→PDF conversion failed: {e}")

    return None


def _search_clause(
    doc: fitz.Document,
    text: str,
    target_page: int | None,
) -> list[dict]:
    """Search for clause text in PDF, returning highlight rects."""
    clean = " ".join(text.split())

    # Pages to search: target page first, then adjacent, then all
    pages_to_try = []
    if target_page and 1 <= target_page <= len(doc):
        pages_to_try.append(target_page - 1)  # fitz is 0-based
        if target_page < len(doc):
            pages_to_try.append(target_page)
        if target_page > 1:
            pages_to_try.insert(1, target_page - 2)
    else:
        pages_to_try = list(range(min(len(doc), 50)))

    # Try progressively shorter text prefixes
    search_lengths = [200, 120, 80, 50, 30]
    search_texts = []
    for length in search_lengths:
        if len(clean) >= length:
            search_texts.append(clean[:length])
    if not search_texts:
        search_texts = [clean]

    for search_text in search_texts:
        for page_idx in pages_to_try:
            page = doc[page_idx]
            found = page.search_for(search_text)
            if found:
                return [
                    {
                        "page": page_idx + 1,  # 1-based
                        "x0": round(r.x0, 2),
                        "y0": round(r.y0, 2),
                        "x1": round(r.x1, 2),
                        "y1": round(r.y1, 2),
                    }
                    for r in found
                ]

    return []
