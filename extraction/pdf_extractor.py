"""PDF text extraction using PyMuPDF.

Extracts text page by page (preserving page numbers), detects PDFs that are
password-protected, empty, or scanned (image-only, needing OCR), and joins
pages into a single labelled text block for the LLM.
"""

from dataclasses import dataclass
from typing import List

import pymupdf

import config


class PDFExtractionError(Exception):
    """Raised when a PDF cannot be opened or read."""


OCR_REQUIRED_MESSAGE = (
    "This PDF appears to be scanned or image-based: no machine-readable text "
    "could be extracted from it. Reading it would require OCR (optical "
    "character recognition), which this application does not perform. "
    "Please upload a text-based PDF or paste the report text manually."
)


@dataclass
class PageText:
    """Text of one PDF page. page_number is 1-based, as printed on the report."""

    page_number: int
    text: str


def extract_pdf_text(data: bytes) -> List[PageText]:
    """Extract text from every page of a PDF given as raw bytes."""
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PDFExtractionError(
            "The uploaded file could not be opened as a PDF. "
            "Please upload a valid, uncorrupted PDF file."
        ) from exc

    try:
        if document.needs_pass:
            raise PDFExtractionError(
                "This PDF is password-protected. Please remove the password "
                "and upload it again."
            )
        pages = [
            PageText(page_number=index, text=page.get_text("text").strip())
            for index, page in enumerate(document, start=1)
        ]
    finally:
        document.close()

    if not pages:
        raise PDFExtractionError("The PDF contains no pages.")
    return pages


def is_probably_scanned(pages: List[PageText]) -> bool:
    """True when the whole PDF holds almost no extractable text (scanned/image PDF)."""
    total_chars = sum(len(page.text) for page in pages)
    return total_chars < config.SCANNED_PDF_CHAR_THRESHOLD


def combine_pages(pages: List[PageText]) -> str:
    """Join pages with explicit page labels so the LLM can report page numbers."""
    blocks = [f"--- PAGE {page.page_number} ---\n{page.text}" for page in pages]
    return "\n\n".join(blocks)
