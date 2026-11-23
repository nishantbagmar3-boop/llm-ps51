"""Unit tests for PDF/TXT extraction, scanned-PDF detection and validators."""

import pymupdf
import pytest

import config
from extraction import pdf_extractor, text_extractor
from extraction.pdf_extractor import PDFExtractionError
from extraction.text_extractor import TextExtractionError
from utils import validators


# --------------------------------------------------------------------------- #
# Helpers: build small PDFs in memory
# --------------------------------------------------------------------------- #
def pdf_bytes_with_text(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(40, 40, 555, 800), text, fontsize=10)
    data = document.tobytes()
    document.close()
    return data


def blank_pdf_bytes() -> bytes:
    document = pymupdf.open()
    document.new_page()
    data = document.tobytes()
    document.close()
    return data


# --------------------------------------------------------------------------- #
# TXT extraction
# --------------------------------------------------------------------------- #
def test_txt_utf8_roundtrip():
    text = text_extractor.extract_txt_text("Hemoglobin 10.5 g/dL".encode("utf-8"))
    assert "Hemoglobin" in text


def test_txt_cp1252_fallback():
    data = "Café résults 10.5".encode("cp1252")
    text = text_extractor.extract_txt_text(data)
    assert "10.5" in text


def test_txt_empty_raises():
    with pytest.raises(TextExtractionError):
        text_extractor.extract_txt_text(b"   \n  \n")


def test_clean_text_collapses_blank_lines_and_crlf():
    cleaned = text_extractor.clean_report_text("a\r\n\r\n\r\n\r\nb\r\n")
    assert cleaned == "a\n\nb"


def test_clean_text_truncates_very_long_reports():
    cleaned = text_extractor.clean_report_text("x" * (config.MAX_REPORT_CHARS + 500))
    assert len(cleaned) <= config.MAX_REPORT_CHARS + 50
    assert cleaned.endswith("[REPORT TRUNCATED]")


# --------------------------------------------------------------------------- #
# PDF extraction
# --------------------------------------------------------------------------- #
def test_pdf_text_is_extracted_with_page_numbers():
    pages = pdf_extractor.extract_pdf_text(pdf_bytes_with_text("Hemoglobin 10.5 g/dL"))
    assert pages[0].page_number == 1
    assert "Hemoglobin" in pages[0].text


def test_invalid_pdf_bytes_raise():
    with pytest.raises(PDFExtractionError):
        pdf_extractor.extract_pdf_text(b"this is definitely not a pdf")


def test_blank_pdf_detected_as_scanned():
    pages = pdf_extractor.extract_pdf_text(blank_pdf_bytes())
    assert pdf_extractor.is_probably_scanned(pages) is True


def test_text_pdf_not_detected_as_scanned():
    pages = pdf_extractor.extract_pdf_text(
        pdf_bytes_with_text("Hemoglobin 10.5 g/dL  Reference 12.0 - 16.0 g/dL")
    )
    assert pdf_extractor.is_probably_scanned(pages) is False


def test_combine_pages_labels_each_page():
    pages = [
        pdf_extractor.PageText(1, "first"),
        pdf_extractor.PageText(2, "second"),
    ]
    combined = pdf_extractor.combine_pages(pages)
    assert "--- PAGE 1 ---" in combined
    assert "--- PAGE 2 ---" in combined


# --------------------------------------------------------------------------- #
# Upload / text validators
# --------------------------------------------------------------------------- #
def test_validate_upload_rejects_wrong_extension():
    ok, message = validators.validate_upload("report.docx", 1000)
    assert not ok and "Unsupported" in message


def test_validate_upload_rejects_oversize():
    ok, message = validators.validate_upload(
        "report.pdf", config.MAX_FILE_SIZE_BYTES + 1
    )
    assert not ok and "limit" in message


def test_validate_upload_rejects_empty_file():
    ok, _ = validators.validate_upload("report.pdf", 0)
    assert not ok


def test_validate_upload_accepts_valid_pdf():
    ok, _ = validators.validate_upload("report.pdf", 1024)
    assert ok


def test_validate_report_text_rejects_empty_and_short():
    ok_empty, _ = validators.validate_report_text("   ")
    ok_short, _ = validators.validate_report_text("hi")
    assert not ok_empty and not ok_short


def test_validate_report_text_accepts_real_text():
    ok, _ = validators.validate_report_text("Hemoglobin 10.5 g/dL (12.0 - 16.0)")
    assert ok
