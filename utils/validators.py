"""Input validation for uploaded files and pasted text."""

from pathlib import Path
from typing import Tuple

import config


def validate_upload(filename: str, size_bytes: int) -> Tuple[bool, str]:
    """Check extension and size of an uploaded file. Returns (ok, message)."""
    extension = Path(filename or "").suffix.lower()
    if extension not in config.ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(config.ALLOWED_EXTENSIONS))
        return False, (
            f"Unsupported file type '{extension or '(none)'}'. "
            f"Supported formats: {allowed}."
        )
    if size_bytes == 0:
        return False, "The uploaded file is empty."
    if size_bytes > config.MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, (
            f"The file is {size_mb:.1f} MB — the limit is "
            f"{config.MAX_FILE_SIZE_MB} MB."
        )
    return True, "OK"


def validate_report_text(text: str) -> Tuple[bool, str]:
    """Check that pasted/extracted text is non-empty and long enough to be a
    report. Returns (ok, message)."""
    stripped = (text or "").strip()
    if not stripped:
        return False, "No report text was provided. Please upload a file or paste your report."
    if len(stripped) < config.MIN_REPORT_CHARS:
        return False, (
            "The provided text is too short to be a medical report. "
            "Please paste the full report text."
        )
    return True, "OK"
