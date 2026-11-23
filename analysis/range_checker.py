"""Deterministic (non-LLM) classification of measured values against the
reference ranges printed on the uploaded report.

This is the core safety property of the application: the LLM never decides
whether a value is LOW, NORMAL or HIGH. Plain Python code does, so the
classification is reproducible, testable and auditable.

Classification rules:
  value <  minimum                -> LOW
  value >  maximum                -> HIGH
  otherwise (boundaries included) -> NORMAL
  no usable reference range       -> NOT EVALUATED
  qualitative / missing value     -> NOT EVALUATED
  ambiguous range or unit clash   -> REFERENCE RANGE NEEDS REVIEW
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from extraction.models import BloodTest, ReferenceInterval

STATUS_LOW = "LOW"
STATUS_NORMAL = "NORMAL"
STATUS_HIGH = "HIGH"
STATUS_NOT_EVALUATED = "NOT EVALUATED"
STATUS_NEEDS_REVIEW = "REFERENCE RANGE NEEDS REVIEW"

ALL_STATUSES = (
    STATUS_LOW,
    STATUS_NORMAL,
    STATUS_HIGH,
    STATUS_NOT_EVALUATED,
    STATUS_NEEDS_REVIEW,
)


@dataclass
class RangeCheckResult:
    """Outcome of checking one test: the status plus a human-readable reason."""

    status: str
    reason: str
    interval_used: Optional[ReferenceInterval] = None


# --------------------------------------------------------------------------- #
# Unit handling
# --------------------------------------------------------------------------- #
def normalise_unit(unit: Optional[str]) -> str:
    """Normalise a unit string for comparison (case, spaces, micro symbols)."""
    if not unit:
        return ""
    text = unit.strip().lower()
    text = text.replace("µ", "u").replace("μ", "u")
    for char in (" ", ".", ","):
        text = text.replace(char, "")
    return text


def units_compatible(value_unit: Optional[str], reference_unit: Optional[str]) -> bool:
    """Units are comparable when equal after normalisation, or when the
    reference interval does not state a unit of its own (labs print the range
    in the same unit as the value on the same line)."""
    reference = normalise_unit(reference_unit)
    if not reference:
        return True
    return normalise_unit(value_unit) == reference


# --------------------------------------------------------------------------- #
# Interval selection
# --------------------------------------------------------------------------- #
def _is_usable(interval: ReferenceInterval) -> bool:
    return interval.minimum is not None or interval.maximum is not None


def choose_interval(
    intervals: List[ReferenceInterval],
) -> Tuple[Optional[ReferenceInterval], str]:
    """Pick the applicable reference interval, or explain why none can be used.

    - no usable interval  -> (None, "no reference range ...")
    - exactly one         -> use it; if it carries a printed condition
                             (e.g. "adult female") it is still the single
                             range the lab printed for this result line.
    - several intervals   -> (None, "multiple ...") — the app never infers
                             patient age or sex, so it cannot pick one safely.
    """
    usable = [interval for interval in intervals if _is_usable(interval)]
    if not usable:
        return None, "no reference range was provided in the report"
    if len(usable) == 1:
        return usable[0], "single reference interval printed on the report"
    return None, (
        "multiple reference intervals (e.g. age- or sex-specific) are printed "
        "and the correct one cannot be determined without patient context"
    )


# --------------------------------------------------------------------------- #
# Core comparison
# --------------------------------------------------------------------------- #
def classify_value(
    value: float, minimum: Optional[float], maximum: Optional[float]
) -> str:
    """Compare a numeric value against (possibly open-ended) bounds.

    A value exactly equal to either boundary counts as NORMAL.
    """
    if minimum is not None and value < minimum:
        return STATUS_LOW
    if maximum is not None and value > maximum:
        return STATUS_HIGH
    return STATUS_NORMAL


def check_test(test: BloodTest) -> RangeCheckResult:
    """Classify one extracted test. This is the single reusable entry point
    used by the analyzer, the UI and the unit tests."""
    # 1. Qualitative or missing value -> nothing numeric to compare.
    if test.value is None:
        if test.value_text:
            return RangeCheckResult(
                STATUS_NOT_EVALUATED,
                f"qualitative result ('{test.value_text}') — "
                "not compared against a numeric range",
            )
        return RangeCheckResult(
            STATUS_NOT_EVALUATED, "no measured value was found in the report"
        )

    # 2. Invalid numeric value (NaN / infinity).
    if not math.isfinite(test.value):
        return RangeCheckResult(
            STATUS_NOT_EVALUATED, "the measured value is not a valid number"
        )

    # 3. Choose the reference interval printed on the report.
    interval, selection_reason = choose_interval(test.reference_intervals)
    if interval is None:
        if "multiple" in selection_reason:
            return RangeCheckResult(STATUS_NEEDS_REVIEW, selection_reason)
        return RangeCheckResult(STATUS_NOT_EVALUATED, selection_reason)

    # 4. Reject an inverted range (min > max): extraction or printing issue.
    if (
        interval.minimum is not None
        and interval.maximum is not None
        and interval.minimum > interval.maximum
    ):
        return RangeCheckResult(
            STATUS_NEEDS_REVIEW,
            "the reference range minimum is greater than its maximum — "
            "likely an extraction or printing problem",
            interval,
        )

    # 5. Units must be compatible before any comparison.
    if not units_compatible(test.unit, interval.unit):
        return RangeCheckResult(
            STATUS_NEEDS_REVIEW,
            f"the value unit '{test.unit}' and the reference range unit "
            f"'{interval.unit}' are not compatible",
            interval,
        )

    # 6. Deterministic comparison.
    status = classify_value(test.value, interval.minimum, interval.maximum)
    reason = "value compared against the reference range printed on the report"
    if interval.condition:
        reason += f" (interval condition as printed: {interval.condition})"
    return RangeCheckResult(status, reason, interval)
