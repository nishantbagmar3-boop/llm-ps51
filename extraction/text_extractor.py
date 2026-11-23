"""Plain-text report reading and cleanup."""

import config


class TextExtractionError(Exception):
    """Raised when a text file cannot be decoded or is empty."""


# utf-8-sig first so a Windows BOM is removed instead of leaking into the text.
_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def extract_txt_text(data: bytes) -> str:
    """Decode an uploaded .txt file and return cleaned report text."""
    text = None
    for encoding in _ENCODINGS:
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise TextExtractionError(
            "The text file could not be decoded. Please save it as UTF-8 and retry."
        )

    cleaned = clean_report_text(text)
    if not cleaned:
        raise TextExtractionError("The text file is empty.")
    return cleaned


def clean_report_text(text: str) -> str:
    """Normalise line endings, trim trailing spaces, collapse blank-line runs,
    and cap the length so the LLM prompt stays within a safe size."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "\n".join(line.rstrip() for line in text.split("\n")).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    if len(cleaned) > config.MAX_REPORT_CHARS:
        cleaned = cleaned[: config.MAX_REPORT_CHARS] + "\n[REPORT TRUNCATED]"
    return cleaned
