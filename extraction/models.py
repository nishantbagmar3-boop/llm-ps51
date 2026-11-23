"""Pydantic models that define and validate the structured JSON returned by
the LLM during extraction.

Validation happens BEFORE any analysis: if the LLM output does not match this
schema, the app attempts one limited repair pass and otherwise reports a
clear error instead of processing unreliable data.
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ReferenceInterval(BaseModel):
    """One reference interval as printed on the report.

    Open-ended ranges are supported: e.g. "< 200" has only a maximum and
    "> 60" has only a minimum. ``condition`` preserves applicability text
    such as "adult female" when the report prints several intervals.
    """

    minimum: Optional[float] = None
    maximum: Optional[float] = None
    unit: Optional[str] = None
    condition: Optional[str] = None


class BloodTest(BaseModel):
    """One test row extracted from the report."""

    test_name: str
    value: Optional[float] = None        # numeric measured value, if numeric
    value_text: Optional[str] = None     # qualitative result, e.g. "Negative"
    unit: Optional[str] = None
    reference_intervals: List[ReferenceInterval] = Field(default_factory=list)
    original_value_text: Optional[str] = None
    original_reference_text: Optional[str] = None
    page_number: Optional[int] = None
    extraction_confidence: str = "high"

    @model_validator(mode="before")
    @classmethod
    def _rescue_qualitative_value(cls, data):
        """If the LLM puts a non-numeric string in ``value`` (e.g. "Positive"),
        move it to ``value_text`` instead of failing validation."""
        if isinstance(data, dict) and isinstance(data.get("value"), str):
            raw = data["value"].strip()
            try:
                data["value"] = float(raw.replace(",", ""))
            except ValueError:
                data["value"] = None
                if not data.get("value_text"):
                    data["value_text"] = raw
        return data

    @field_validator("extraction_confidence", mode="before")
    @classmethod
    def _normalise_confidence(cls, confidence):
        """Clamp confidence to high/medium/low; anything unexpected becomes low."""
        text = str(confidence or "").strip().lower()
        return text if text in {"high", "medium", "low"} else "low"


class PatientInfo(BaseModel):
    patient_name: Optional[str] = None
    report_date: Optional[str] = None


class ExtractedReport(BaseModel):
    """Top-level structure the LLM must return."""

    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    tests: List[BloodTest] = Field(default_factory=list)
