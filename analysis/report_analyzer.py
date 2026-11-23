"""Runs the deterministic range checker over every extracted test and prepares
the dataframes, summaries and export payloads used by the UI and downloads.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

import config
from analysis import range_checker
from analysis.range_checker import RangeCheckResult
from extraction.models import BloodTest, ExtractedReport, ReferenceInterval


@dataclass
class AnalyzedTest:
    """One extracted test together with its Python-calculated status."""

    test: BloodTest
    check: RangeCheckResult

    @property
    def status(self) -> str:
        return self.check.status


def analyze_report(report: ExtractedReport) -> List[AnalyzedTest]:
    """Classify every test in the extracted report."""
    return [
        AnalyzedTest(test=test, check=range_checker.check_test(test))
        for test in report.tests
    ]


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def format_value(test: BloodTest) -> str:
    if test.value is not None:
        return f"{test.value:g}"
    if test.value_text:
        return test.value_text
    return "—"


def _format_interval(interval: ReferenceInterval) -> str:
    if interval.minimum is not None and interval.maximum is not None:
        text = f"{interval.minimum:g} – {interval.maximum:g}"
    elif interval.maximum is not None:
        text = f"< {interval.maximum:g}"
    elif interval.minimum is not None:
        text = f"> {interval.minimum:g}"
    else:
        return "Not provided"
    if interval.unit:
        text += f" {interval.unit}"
    if interval.condition:
        text += f" ({interval.condition})"
    return text


def format_reference(analyzed: AnalyzedTest) -> str:
    """Prefer the range text exactly as printed on the report."""
    test = analyzed.test
    if test.original_reference_text:
        return test.original_reference_text
    intervals = [iv for iv in test.reference_intervals]
    if intervals:
        return "; ".join(_format_interval(iv) for iv in intervals)
    return "Not provided"


# --------------------------------------------------------------------------- #
# Tabular views and summaries
# --------------------------------------------------------------------------- #
def results_dataframe(analyzed_tests: List[AnalyzedTest]) -> pd.DataFrame:
    rows = []
    for analyzed in analyzed_tests:
        test = analyzed.test
        rows.append(
            {
                "Test": test.test_name,
                "Value": format_value(test),
                "Unit": test.unit or "—",
                "Reference Range": format_reference(analyzed),
                "Status": analyzed.status,
                "Confidence": test.extraction_confidence,
                "Page": test.page_number if test.page_number is not None else "—",
            }
        )
    return pd.DataFrame(rows)


def summary_counts(analyzed_tests: List[AnalyzedTest]) -> dict:
    counts = {status: 0 for status in range_checker.ALL_STATUSES}
    for analyzed in analyzed_tests:
        counts[analyzed.status] += 1
    return {
        "total": len(analyzed_tests),
        "normal": counts[range_checker.STATUS_NORMAL],
        "high": counts[range_checker.STATUS_HIGH],
        "low": counts[range_checker.STATUS_LOW],
        "not_evaluated": counts[range_checker.STATUS_NOT_EVALUATED],
        "needs_review": counts[range_checker.STATUS_NEEDS_REVIEW],
    }


# --------------------------------------------------------------------------- #
# Payloads for the LLM explanation step and for exports
# --------------------------------------------------------------------------- #
def explanation_input(analyzed_tests: List[AnalyzedTest]) -> List[dict]:
    """Compact, JSON-able summary of the Python-analysed results, used as the
    fixed input to the LLM explanation prompt."""
    payload = []
    for analyzed in analyzed_tests:
        test = analyzed.test
        payload.append(
            {
                "test_name": test.test_name,
                "measured_value": format_value(test),
                "unit": test.unit,
                "reference_range": format_reference(analyzed),
                "status": analyzed.status,
                "status_reason": analyzed.check.reason,
            }
        )
    return payload


def export_payload(
    report: ExtractedReport,
    analyzed_tests: List[AnalyzedTest],
    explanations: Optional[dict] = None,
) -> dict:
    """Full structured payload for the JSON download (and the PDF builder).

    ``explanations`` maps test_name -> ExplanationItem-like dict.
    """
    explanations = explanations or {}
    tests = []
    for analyzed in analyzed_tests:
        test = analyzed.test
        item = {
            "test_name": test.test_name,
            "value": test.value,
            "value_text": test.value_text,
            "unit": test.unit,
            "original_value_text": test.original_value_text,
            "original_reference_text": test.original_reference_text,
            "reference_intervals": [
                interval.model_dump() for interval in test.reference_intervals
            ],
            "page_number": test.page_number,
            "extraction_confidence": test.extraction_confidence,
            "status": analyzed.status,
            "status_reason": analyzed.check.reason,
        }
        explanation = explanations.get(test.test_name)
        if explanation:
            item["explanation"] = explanation
        tests.append(item)

    return {
        "application": config.APP_NAME,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": config.DISCLAIMER,
        "patient_info": report.patient_info.model_dump(),
        "summary": summary_counts(analyzed_tests),
        "tests": tests,
    }
