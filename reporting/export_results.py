"""JSON and CSV export builders.

Everything is built in memory for Streamlit download buttons — uploaded
reports and results are never stored on disk by the application.
"""

import json
from datetime import datetime
from typing import List

import pandas as pd

import config
from analysis.report_analyzer import AnalyzedTest, format_reference, format_value


def build_json_export(payload: dict) -> str:
    """Serialise the analyzer's export payload (already includes disclaimer,
    original reference texts and Python-calculated statuses)."""
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_csv_export(analyzed_tests: List[AnalyzedTest]) -> str:
    """CSV with the original reference ranges and calculated statuses.
    The disclaimer travels as comment lines above the table."""
    rows = []
    for analyzed in analyzed_tests:
        test = analyzed.test
        rows.append(
            {
                "Test": test.test_name,
                "Value": format_value(test),
                "Unit": test.unit or "",
                "Reference Range (as printed)": format_reference(analyzed),
                "Status (Python-calculated)": analyzed.status,
                "Status Reason": analyzed.check.reason,
                "Extraction Confidence": test.extraction_confidence,
                "Page": test.page_number if test.page_number is not None else "",
            }
        )
    table = pd.DataFrame(rows).to_csv(index=False)
    header = f"# {config.APP_NAME}\n# {config.DISCLAIMER}\n"
    return header + table


def timestamped_filename(stem: str, extension: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{stamp}.{extension}"
