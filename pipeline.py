"""End-to-end analysis pipeline.

Connects the stages in the required order and is used by BOTH the Streamlit
app and the test scripts, so they always run exactly the same logic:

  1. report text  ->  LLM structured extraction (Gemini, JSON only)
  2. JSON         ->  Pydantic validation (one limited repair attempt)
  3. tests        ->  deterministic Python range checking (no LLM involved)
  4. statuses     ->  LLM simple explanations (statuses are fixed input)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from ai.explanation_prompt import (
    ExplanationItem,
    ExplanationSet,
    build_explanation_prompt,
)
from ai.extraction_prompt import build_extraction_prompt
from ai.gemini_client import GeminiClient
from analysis import report_analyzer
from analysis.report_analyzer import AnalyzedTest
from extraction import json_parser
from extraction.models import ExtractedReport


@dataclass
class PipelineResult:
    report: ExtractedReport
    analyzed: List[AnalyzedTest]
    explanations: Dict[str, ExplanationItem] = field(default_factory=dict)
    raw_extraction_json: str = ""


def run_extraction(
    client: GeminiClient, report_text: str
) -> Tuple[ExtractedReport, str]:
    """Stage 1+2: LLM extraction followed by Pydantic validation."""
    prompt = build_extraction_prompt(report_text)
    raw = client.generate_json(prompt)
    report = json_parser.parse_and_validate(raw, repair_fn=client.make_repair_fn())
    return report, raw


def run_explanations(
    client: GeminiClient, analyzed: List[AnalyzedTest]
) -> Dict[str, ExplanationItem]:
    """Stage 4: patient-friendly explanations for already-classified results.

    The Python-calculated status is part of the prompt input and is never
    taken from the LLM output — the UI and exports always display the status
    computed by analysis.range_checker.
    """
    if not analyzed:
        return {}
    prompt = build_explanation_prompt(report_analyzer.explanation_input(analyzed))
    raw = client.generate_json(prompt)

    def _validate(raw_text: str) -> ExplanationSet:
        data = json_parser.parse_llm_json(raw_text)
        return ExplanationSet.model_validate(data)

    try:
        parsed = _validate(raw)
    except (json_parser.JSONParsingError, ValidationError) as first_error:
        repaired = client.make_repair_fn()(raw, str(first_error))
        parsed = _validate(repaired)  # a second failure propagates as an error

    return {item.test_name: item for item in parsed.explanations}


def analyze_text(
    report_text: str,
    client: Optional[GeminiClient] = None,
    with_explanations: bool = True,
) -> PipelineResult:
    """Run the full pipeline over cleaned report text."""
    client = client or GeminiClient()
    report, raw = run_extraction(client, report_text)
    analyzed = report_analyzer.analyze_report(report)
    explanations = (
        run_explanations(client, analyzed) if (with_explanations and analyzed) else {}
    )
    return PipelineResult(
        report=report,
        analyzed=analyzed,
        explanations=explanations,
        raw_extraction_json=raw,
    )
