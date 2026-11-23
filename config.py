"""Central configuration for the Medical Report Explainer.

Loads environment variables from the project .env file and exposes
application-wide constants used by the extraction, AI, analysis and
reporting modules.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

# Variables are read from <project>/.env — that file is never committed.
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# LLM settings
# ---------------------------------------------------------------------------
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = (os.getenv("GEMINI_MODEL") or "").strip() or "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Upload limits
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

# Reports longer than this are truncated before being sent to the LLM so a
# single prompt stays within a safe size.
MAX_REPORT_CHARS = 60_000

# A PDF whose pages together contain fewer characters than this is treated
# as a scanned/image-only PDF that would need OCR.
SCANNED_PDF_CHAR_THRESHOLD = 40

# Pasted text shorter than this cannot meaningfully be analysed as a report.
MIN_REPORT_CHARS = 20

APP_NAME = "Medical Report Explainer"

DISCLAIMER = (
    "DISCLAIMER: This application is designed for educational and informational "
    "purposes only. It does not provide medical diagnoses, treatment "
    "recommendations, or professional medical advice. Blood test results must be "
    "interpreted by a qualified healthcare professional considering your medical "
    "history, symptoms, age, and other relevant factors. Please consult your "
    "doctor for proper interpretation of your results."
)

API_KEY_SETUP_MESSAGE = (
    "GEMINI_API_KEY is not configured.\n\n"
    "How to set it up:\n"
    "1. Get a free API key from Google AI Studio: https://aistudio.google.com/apikey\n"
    "2. In the project folder, copy .env.example to a file named .env\n"
    "3. Open .env and set:  GEMINI_API_KEY=your_real_key\n"
    "4. Restart the application.\n\n"
    "The key is read from the .env file (via python-dotenv) and is never "
    "hard-coded or committed to git."
)


def api_key_available() -> bool:
    """True when a Gemini API key has been configured."""
    return bool(GEMINI_API_KEY)
