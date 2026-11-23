"""Builds the prompt that asks Gemini for patient-friendly explanations of
results that Python has already classified, plus the Pydantic models used to
validate the explanation JSON.

The LOW/NORMAL/HIGH status is computed deterministically in
analysis.range_checker — the LLM receives the status as fixed input and is
explicitly forbidden from changing or contradicting it.
"""

import json
from typing import List

from pydantic import BaseModel, Field

EXPLANATION_SCHEMA = """{
  "explanations": [
    {
      "test_name": "string — copied EXACTLY from the input",
      "what_it_measures": "string — 1-2 simple sentences on what this test measures",
      "result_explanation": "string — 2-4 simple sentences about THIS patient's result and its given STATUS",
      "doctor_discussion": "string — 1-2 sentences on why/how to discuss this result with a doctor",
      "needs_professional_review": "boolean — true when the result should be reviewed by a healthcare professional"
    }
  ]
}"""


class ExplanationItem(BaseModel):
    test_name: str
    what_it_measures: str = ""
    result_explanation: str = ""
    doctor_discussion: str = ""
    needs_professional_review: bool = True


class ExplanationSet(BaseModel):
    explanations: List[ExplanationItem] = Field(default_factory=list)


def build_explanation_prompt(analyzed_tests: List[dict]) -> str:
    """Return the explanation prompt for the already-analysed tests.

    ``analyzed_tests`` is the compact summary produced by
    analysis.report_analyzer.explanation_input — it already contains the
    Python-calculated status for each test.
    """
    payload = json.dumps(analyzed_tests, indent=2, ensure_ascii=False)
    return f"""You are a medical communication assistant. Your job is to explain
blood test results in simple, calm, everyday English that an ordinary patient
with no medical background can understand.

Each test below has already been analysed by deterministic software. The
"status" field (LOW, NORMAL, HIGH, NOT EVALUATED, or REFERENCE RANGE NEEDS
REVIEW) was calculated by Python code comparing the measured value against the
reference range printed on the patient's own report. That status is FINAL.

STRICT MEDICAL RULES — follow every rule:
1. NEVER change, question or contradict the given status of any test.
2. NEVER diagnose any disease or medical condition.
3. NEVER claim that one abnormal value proves or indicates a disease.
4. NEVER prescribe, name or suggest medicines.
5. NEVER recommend starting, stopping or changing any medication.
6. NEVER recommend treatment of any kind.
7. Do NOT be frightening, alarming or exaggerated. Stay calm and neutral.
8. Do NOT claim a normal result guarantees good health.
9. Mention, where natural, that interpretation depends on age, sex, symptoms,
   medical history and other relevant factors that only a doctor can assess.
10. For a LOW or HIGH status: say the value is below/above the reference range
    printed on the report, explain in general terms what the test measures,
    and recommend discussing the result with a healthcare professional.
11. For NOT EVALUATED: explain that the value could not be compared because no
    reference range was available (or the result is qualitative), so a doctor
    should interpret it.
12. For REFERENCE RANGE NEEDS REVIEW: explain that the applicable reference
    interval could not be determined automatically and a professional should
    review it. Be clear about this uncertainty.
13. Use short sentences and plain words. Avoid medical jargon; where a medical
    term is needed, explain it simply.
14. Set "needs_professional_review" to true for every test whose status is not
    NORMAL, and for any result you are uncertain about.
15. Produce EXACTLY one explanation object per input test, in the same order,
    copying each "test_name" exactly.

TESTS ANALYSED BY PYTHON (statuses are final):
{payload}

Return ONE valid JSON object with exactly this structure — JSON only, no
commentary, no markdown, no code fences:

{EXPLANATION_SCHEMA}"""
