"""Generate the PDF sample inputs from the synthetic text samples.

Creates:
  sample_reports/sample_report.pdf   — a text-based PDF (normal upload path)
  sample_reports/scanned_report.pdf  — an image-only page with NO extractable
                                       text, to exercise the OCR-required path

Run from the project root:  python scripts/make_sample_pdfs.py
"""

import sys
from pathlib import Path

import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES = PROJECT_ROOT / "sample_reports"


def make_text_pdf() -> Path:
    source = (SAMPLES / "sample_report.txt").read_text(encoding="utf-8")
    target = SAMPLES / "sample_report.pdf"
    document = pymupdf.open()
    page = document.new_page()  # A4 by default (595 x 842 points)
    rect = pymupdf.Rect(40, 40, 555, 802)
    page.insert_textbox(rect, source, fontsize=9, fontname="cour")
    document.save(target)
    document.close()
    return target


def make_scanned_pdf() -> Path:
    """A page containing only drawings (no text objects) — behaves like a
    scanned report: PyMuPDF extracts zero text from it."""
    target = SAMPLES / "scanned_report.pdf"
    document = pymupdf.open()
    page = document.new_page()
    # Grey rectangles standing in for a photographed report.
    for top in range(80, 700, 40):
        page.draw_rect(
            pymupdf.Rect(60, top, 540, top + 18),
            color=(0.75, 0.75, 0.75),
            fill=(0.88, 0.88, 0.88),
        )
    document.save(target)
    document.close()
    return target


if __name__ == "__main__":
    text_pdf = make_text_pdf()
    scanned_pdf = make_scanned_pdf()
    print(f"created: {text_pdf}")
    print(f"created: {scanned_pdf}")
    sys.exit(0)
