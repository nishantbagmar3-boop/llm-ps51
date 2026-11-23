"""Unit tests for LLM JSON parsing, Pydantic validation and the repair path."""

import json

import pytest

from extraction import json_parser
from extraction.json_parser import JSONParsingError, parse_and_validate

VALID_PAYLOAD = {
    "patient_info": {"patient_name": "SAMPLE PATIENT", "report_date": "15-Nov-2026"},
    "tests": [
        {
            "test_name": "Hemoglobin",
            "value": 10.5,
            "unit": "g/dL",
            "reference_intervals": [{"minimum": 12.0, "maximum": 16.0}],
            "original_value_text": "10.5 g/dL",
            "original_reference_text": "12.0 - 16.0 g/dL",
            "page_number": 1,
            "extraction_confidence": "high",
        }
    ],
}


def test_plain_valid_json_parses():
    report = parse_and_validate(json.dumps(VALID_PAYLOAD))
    assert len(report.tests) == 1
    assert report.tests[0].test_name == "Hemoglobin"
    assert report.tests[0].reference_intervals[0].maximum == 16.0


def test_markdown_fenced_json_parses():
    raw = "```json\n" + json.dumps(VALID_PAYLOAD) + "\n```"
    report = parse_and_validate(raw)
    assert report.patient_info.patient_name == "SAMPLE PATIENT"


def test_json_with_surrounding_prose_parses():
    raw = "Here is the data:\n" + json.dumps(VALID_PAYLOAD) + "\nHope this helps!"
    report = parse_and_validate(raw)
    assert report.tests[0].value == 10.5


def test_numeric_string_value_is_coerced():
    payload = json.loads(json.dumps(VALID_PAYLOAD))
    payload["tests"][0]["value"] = "10.5"
    report = parse_and_validate(json.dumps(payload))
    assert report.tests[0].value == 10.5


def test_qualitative_string_in_value_is_rescued_to_value_text():
    payload = json.loads(json.dumps(VALID_PAYLOAD))
    payload["tests"][0]["value"] = "Positive"
    report = parse_and_validate(json.dumps(payload))
    assert report.tests[0].value is None
    assert report.tests[0].value_text == "Positive"


def test_unknown_confidence_becomes_low():
    payload = json.loads(json.dumps(VALID_PAYLOAD))
    payload["tests"][0]["extraction_confidence"] = "very sure!!"
    report = parse_and_validate(json.dumps(payload))
    assert report.tests[0].extraction_confidence == "low"


def test_empty_response_raises():
    with pytest.raises(JSONParsingError):
        parse_and_validate("   ")


def test_malformed_json_without_repair_raises():
    with pytest.raises(JSONParsingError):
        parse_and_validate('{"patient_info": {, "tests": []}')


def test_schema_mismatch_raises():
    with pytest.raises(JSONParsingError):
        parse_and_validate('{"patient_info": {}, "tests": "not-a-list"}')


def test_repair_function_fixes_malformed_json():
    calls = []

    def repair(bad_output, error_message):
        calls.append(error_message)
        return json.dumps(VALID_PAYLOAD)

    report = parse_and_validate('{"broken": ', repair_fn=repair)
    assert len(calls) == 1
    assert report.tests[0].test_name == "Hemoglobin"


def test_failed_repair_raises_clear_error():
    def bad_repair(bad_output, error_message):
        return "still not json {"

    with pytest.raises(JSONParsingError) as excinfo:
        parse_and_validate('{"broken": ', repair_fn=bad_repair)
    assert "repair attempt" in str(excinfo.value)


def test_missing_optional_fields_use_defaults():
    minimal = {"tests": [{"test_name": "Glucose", "value": 92}]}
    report = parse_and_validate(json.dumps(minimal))
    assert report.patient_info.patient_name is None
    assert report.tests[0].reference_intervals == []
    assert report.tests[0].extraction_confidence == "high"


def test_parse_llm_json_rejects_non_object():
    with pytest.raises(JSONParsingError):
        json_parser.parse_llm_json("[1, 2, 3]")
