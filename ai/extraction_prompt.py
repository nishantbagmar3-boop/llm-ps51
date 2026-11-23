"""Builds the prompt that instructs Gemini to extract structured blood-test
data from raw report text as strict JSON.

The schema here must stay in sync with extraction.models — Pydantic validates
every response against those models before any analysis happens.
"""

EXTRACTION_SCHEMA = """{
  "patient_info": {
    "patient_name": "string or null",
    "report_date": "string or null"
  },
  "tests": [
    {
      "test_name": "string — the test name as printed",
      "value": "number or null — the patient's measured NUMERIC value only",
      "value_text": "string or null — qualitative results only, e.g. 'Negative', 'Trace'",
      "unit": "string or null — the unit printed next to the measured value",
      "reference_intervals": [
        {
          "minimum": "number or null",
          "maximum": "number or null",
          "unit": "string or null — unit of the reference range if printed",
          "condition": "string or null — applicability as printed, e.g. 'adult female', 'children 6-12 years'"
        }
      ],
      "original_value_text": "string — the measured value exactly as printed, e.g. '10.5 g/dL'",
      "original_reference_text": "string or null — the reference range exactly as printed, e.g. '12.0 - 16.0 g/dL'",
      "page_number": "integer or null — from the '--- PAGE N ---' marker the test appears under",
      "extraction_confidence": "one of: high | medium | low"
    }
  ]
}"""


def build_extraction_prompt(report_text: str) -> str:
    """Return the full extraction prompt for the given report text."""
    return f"""You are a careful medical laboratory data extraction system.
Your only job is to read the blood test report text below and copy its data
into structured JSON. You never interpret, judge or classify results.

Return ONE valid JSON object with exactly this structure:

{EXTRACTION_SCHEMA}

STRICT EXTRACTION RULES — follow every rule:
1. Extract ONLY information explicitly present in the report text.
2. NEVER invent test values.
3. NEVER invent reference ranges. If no range is printed for a test, use an
   empty list [] for "reference_intervals" and null for "original_reference_text".
4. Preserve the original units exactly as printed.
5. Preserve the original reference-range text exactly as printed.
6. Use null for any information that is unavailable.
7. Do NOT confuse the patient's measured value with the reference range.
   The measured value is the patient's result; the reference range is the
   printed normal interval.
8. Numeric results go in "value" (as a number). Qualitative results such as
   "Positive", "Negative", "Trace", "Reactive" go in "value_text" with
   "value" set to null. Never put text into "value".
9. Reference ranges written as "12.0 - 16.0" have both minimum and maximum.
   Open-ended ranges: "< 200" means minimum=null, maximum=200;
   "> 60" or ">= 60" means minimum=60, maximum=null.
10. If a test prints SEVERAL reference intervals (for example different ranges
    for men, women or age groups), include EACH as its own entry in
    "reference_intervals" and copy its applicability text into "condition".
11. Do NOT infer patient demographics (age, sex) — only copy what is printed.
12. Set "extraction_confidence" to "medium" or "low" whenever a value, unit or
    range is unclear, ambiguous or possibly misread; otherwise "high".
13. If the text contains "--- PAGE N ---" markers, report each test's page
    number from them; otherwise set "page_number" to null.
14. Include every distinct test result found. Do not duplicate tests.
15. Return VALID JSON only — no commentary, no markdown, no code fences.

REPORT TEXT:
--------------------------------------------------
{report_text}
--------------------------------------------------

Return the JSON object now."""
