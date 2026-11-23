"""Run the five required sample inputs through the REAL pipeline (live Gemini
calls) plus the error-path checks, verify the expected Python-calculated
statuses, and record the genuine results in docs/TEST_RESULTS.md.

Usage (from the project root, with GEMINI_API_KEY configured in .env):
    python scripts/run_samples.py

Exits with code 0 only if every expectation holds.
"""

import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
import pipeline  # noqa: E402
from ai.gemini_client import GeminiClient, GeminiClientError  # noqa: E402
from extraction import json_parser, pdf_extractor  # noqa: E402
from utils import validators  # noqa: E402

SAMPLES = PROJECT_ROOT / "sample_reports"
DOCS = PROJECT_ROOT / "docs"
OUTPUTS = DOCS / "sample_outputs"

# (file, [(test-name fragment, expected status), ...])
SAMPLE_EXPECTATIONS = [
    ("test1_hemoglobin_low.txt", [("hemoglobin", "LOW")]),
    ("test2_glucose_normal.txt", [("glucose", "NORMAL")]),
    ("test3_wbc_high.txt", [("wbc", "HIGH")]),
    (
        "test4_mixed_results.txt",
        [
            ("hemoglobin", "LOW"),
            ("wbc", "HIGH"),
            ("platelet", "NORMAL"),
            ("calcium", "NORMAL"),
        ],
    ),
    (
        "test5_missing_range.txt",
        [("vitamin d", "NOT EVALUATED"), ("hba1c", "NORMAL")],
    ),
]


def find_status(analyzed, fragment: str):
    for item in analyzed:
        if fragment.lower() in item.test.test_name.lower():
            return item.status
    return None


def run_sample(client, filename, expectations, lines, failures):
    text = (SAMPLES / filename).read_text(encoding="utf-8")
    started = time.time()
    result = pipeline.analyze_text(text, client=client, with_explanations=True)
    elapsed = time.time() - started

    lines.append(f"\n### {filename}\n")
    lines.append(
        f"- Extracted **{len(result.analyzed)}** test(s) in {elapsed:.1f}s "
        f"(model `{client.model}`, two LLM calls: extraction + explanations)\n"
    )
    lines.append("| Test | Value | Reference (as printed) | Python status | Expected | OK |")
    lines.append("|---|---|---|---|---|---|")

    expected_by_fragment = {fragment: status for fragment, status in expectations}
    for item in result.analyzed:
        from analysis.report_analyzer import format_reference, format_value

        matching_expected = next(
            (
                status
                for fragment, status in expected_by_fragment.items()
                if fragment in item.test.test_name.lower()
            ),
            "",
        )
        ok_mark = ""
        if matching_expected:
            ok_mark = "✅" if item.status == matching_expected else "❌"
        lines.append(
            f"| {item.test.test_name} | {format_value(item.test)} "
            f"{item.test.unit or ''} | {format_reference(item)} "
            f"| **{item.status}** | {matching_expected or '—'} | {ok_mark} |"
        )

    for fragment, expected in expectations:
        actual = find_status(result.analyzed, fragment)
        if actual != expected:
            failures.append(
                f"{filename}: expected '{fragment}' -> {expected}, got {actual}"
            )

    # Explanations must preserve Python's statuses: the app never reads a
    # status from the LLM (there is no status field in the explanation
    # schema), and every analysed test should have an explanation.
    missing = [
        item.test.test_name
        for item in result.analyzed
        if item.test.test_name not in result.explanations
    ]
    if missing:
        failures.append(f"{filename}: no explanation returned for {missing}")
        lines.append(f"\n- ⚠ Missing explanations for: {', '.join(missing)}\n")
    else:
        lines.append(f"\n- Explanations returned for all {len(result.analyzed)} test(s). ✅")

    example = next(iter(result.explanations.values()), None)
    if example:
        snippet = (example.what_it_measures + " " + example.result_explanation).strip()
        lines.append(
            f"- Example explanation (*{example.test_name}*): "
            f"“{snippet[:260]}{'…' if len(snippet) > 260 else ''}”\n"
        )

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / f"{Path(filename).stem}_extraction.json").write_text(
        json.dumps(json.loads(result.report.model_dump_json()), indent=2),
        encoding="utf-8",
    )
    return result


def run_error_paths(lines, failures):
    lines.append("\n### Error-path checks (no fabrication — executed now)\n")

    def check(name, func, expect_exception):
        try:
            outcome = func()
        except expect_exception:
            lines.append(f"- {name}: raised `{expect_exception.__name__}` as expected ✅")
            return
        except Exception as exc:  # wrong exception type
            failures.append(f"{name}: raised unexpected {type(exc).__name__}: {exc}")
            lines.append(f"- {name}: unexpected {type(exc).__name__} ❌")
            return
        if expect_exception is None:
            lines.append(f"- {name}: {outcome} ✅")
        else:
            failures.append(f"{name}: no exception raised")
            lines.append(f"- {name}: expected an error but none was raised ❌")

    check(
        "Invalid PDF upload (random bytes)",
        lambda: pdf_extractor.extract_pdf_text(b"not a real pdf at all"),
        pdf_extractor.PDFExtractionError,
    )

    ok, message = validators.validate_report_text("   ")
    if ok:
        failures.append("Empty text input was accepted")
        lines.append("- Empty text input: accepted ❌")
    else:
        lines.append(f"- Empty text input: rejected with “{message}” ✅")

    scanned = SAMPLES / "scanned_report.pdf"
    pages = pdf_extractor.extract_pdf_text(scanned.read_bytes())
    if pdf_extractor.is_probably_scanned(pages):
        lines.append("- Scanned PDF without extractable text: detected, OCR message shown ✅")
    else:
        failures.append("Scanned PDF was not detected")
        lines.append("- Scanned PDF: NOT detected ❌")

    check(
        "Malformed LLM JSON (no repair available)",
        lambda: json_parser.parse_and_validate('{"broken": '),
        json_parser.JSONParsingError,
    )

    check(
        "Missing API key",
        lambda: GeminiClient(api_key=""),
        GeminiClientError,
    )


def main() -> int:
    if not config.api_key_available():
        print("GEMINI_API_KEY is not configured — cannot run the live sample tests.")
        print(config.API_KEY_SETUP_MESSAGE)
        return 2

    client = GeminiClient()
    lines = [
        "# Test Results — executed sample runs",
        "",
        f"- Date: {datetime.now().strftime('%d %b %Y %H:%M')}",
        f"- Model: `{client.model}` (temperature 0)",
        "- Every row below comes from a live run of scripts/run_samples.py — "
        "statuses are calculated by analysis/range_checker.py in Python, "
        "never by the LLM.",
    ]
    failures: list[str] = []

    for index, (filename, expectations) in enumerate(SAMPLE_EXPECTATIONS):
        if index:
            time.sleep(25)  # free tier allows ~5 requests/min; 2 calls per sample
        try:
            run_sample(client, filename, expectations, lines, failures)
            print(f"done: {filename}")
        except Exception as exc:
            failures.append(f"{filename}: pipeline raised {type(exc).__name__}: {exc}")
            lines.append(f"\n### {filename}\n- ❌ pipeline error: {exc}\n")
            traceback.print_exc()

    run_error_paths(lines, failures)

    lines.append("\n## Verdict\n")
    if failures:
        lines.append(f"**{len(failures)} expectation(s) FAILED:**\n")
        lines.extend(f"- ❌ {failure}" for failure in failures)
    else:
        lines.append("**All sample expectations and error-path checks passed.** ✅")

    DOCS.mkdir(exist_ok=True)
    report_path = DOCS / "TEST_RESULTS.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {report_path}")
    print("FAILURES:" if failures else "ALL PASSED")
    for failure in failures:
        print(f"  - {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
