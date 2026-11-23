"""Parse and validate the LLM's JSON output.

The LLM is instructed to return pure JSON, but models sometimes wrap output
in markdown code fences or add stray text. This module strips that, parses
the JSON, validates it against the Pydantic schema, and optionally retries
once through a caller-supplied repair function (one extra LLM call) when
parsing or validation fails. If the repair also fails, a clear error is
raised instead of processing unreliable data.
"""

import json
from typing import Callable, Optional

from pydantic import ValidationError

from extraction.models import ExtractedReport

# Signature: repair_fn(bad_output, error_message) -> hopefully-fixed output
RepairFn = Callable[[str, str], str]


class JSONParsingError(Exception):
    """Raised when LLM output cannot be turned into a valid ExtractedReport."""


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _extract_json_object(raw: str) -> str:
    """Return the substring from the first '{' to the last '}'."""
    text = _strip_code_fences(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise JSONParsingError("The LLM response contains no JSON object.")
    return text[start : end + 1]


def parse_llm_json(raw: str) -> dict:
    """Parse raw LLM output into a plain dict, or raise JSONParsingError."""
    if not raw or not raw.strip():
        raise JSONParsingError("The LLM returned an empty response.")
    candidate = _extract_json_object(raw)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JSONParsingError(f"Invalid JSON from the LLM: {exc}") from exc
    if not isinstance(data, dict):
        raise JSONParsingError("The LLM returned JSON that is not an object.")
    return data


def validate_extraction(data: dict) -> ExtractedReport:
    """Validate a parsed dict against the Pydantic schema."""
    try:
        return ExtractedReport.model_validate(data)
    except ValidationError as exc:
        raise JSONParsingError(
            f"The LLM JSON did not match the expected schema: {exc}"
        ) from exc


def parse_and_validate(
    raw: str, repair_fn: Optional[RepairFn] = None
) -> ExtractedReport:
    """Parse ``raw`` into a validated ExtractedReport, with one repair attempt."""
    try:
        return validate_extraction(parse_llm_json(raw))
    except JSONParsingError as first_error:
        if repair_fn is None:
            raise
        repaired = repair_fn(raw, str(first_error))
        try:
            return validate_extraction(parse_llm_json(repaired))
        except JSONParsingError as second_error:
            raise JSONParsingError(
                "The LLM did not return valid structured JSON even after one "
                f"repair attempt. Last error: {second_error}"
            ) from second_error
