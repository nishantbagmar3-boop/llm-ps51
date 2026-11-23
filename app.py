"""Medical Report Explainer — Streamlit user interface.

Workflow (see pipeline.py):
  upload/paste -> local text extraction -> LLM structured extraction (Gemini)
  -> Pydantic validation -> deterministic Python range checking
  -> LLM simple explanations -> results, charts and downloads.

The uploaded report is processed in memory only — it is never stored on disk.
"""

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import pipeline
from ai.gemini_client import GeminiClient, GeminiClientError
from analysis import range_checker, report_analyzer
from extraction import json_parser, pdf_extractor, text_extractor
from reporting import export_results, pdf_report
from utils import helpers, validators

# --------------------------------------------------------------------------- #
# Page setup and styling
# --------------------------------------------------------------------------- #
st.set_page_config(page_title=config.APP_NAME, layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; max-width: 1150px; }
      .mre-hero {
        background: linear-gradient(135deg, #E3F0FC 0%, #F7FBFF 100%);
        border: 1px solid #CFE3F7; border-radius: 16px;
        padding: 26px 30px; margin-bottom: 18px;
      }
      .mre-hero h1 { color: #0D47A1; margin: 0 0 6px 0; font-size: 1.9rem; }
      .mre-hero p { color: #33475B; margin: 0; font-size: 1.0rem; }
      .mre-card {
        background: #FFFFFF; border: 1px solid #D9E6F2; border-radius: 14px;
        padding: 18px 20px; margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(13, 71, 161, 0.06);
      }
      .mre-card h4 { margin: 0 0 8px 0; color: #0D47A1; }
      .mre-kv { color: #33475B; font-size: 0.92rem; margin: 2px 0; }
      .mre-kv b { color: #1A2B3C; }
      .mre-exp { color: #1A2B3C; font-size: 0.95rem; line-height: 1.55; margin-top: 10px; }
      .mre-followup {
        background: #F2F8FE; border-left: 4px solid #1565C0; border-radius: 6px;
        padding: 8px 12px; margin-top: 10px; font-size: 0.9rem; color: #33475B;
      }
      .mre-disclaimer {
        background: #FFF8E7; border: 1px solid #E0A800; border-radius: 12px;
        padding: 14px 18px; color: #7A4E00; font-size: 0.9rem; line-height: 1.5;
      }
      .mre-steps li { margin-bottom: 6px; color: #33475B; }
      div[data-testid="stMetric"] {
        background: #F7FBFF; border: 1px solid #D9E6F2; border-radius: 12px;
        padding: 10px 14px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_disclaimer() -> None:
    st.markdown(
        f'<div class="mre-disclaimer">{html.escape(config.DISCLAIMER)}</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Session state
# --------------------------------------------------------------------------- #
DEFAULT_STATE = {
    "nav": "Home",
    "source_name": None,   # filename or "Pasted text"
    "report_text": None,   # cleaned text ready for the LLM
    "input_error": None,   # problem with the current upload/paste
    "result": None,        # pipeline.PipelineResult
    "analysis_error": None,
}
for key, value in DEFAULT_STATE.items():
    st.session_state.setdefault(key, value)


def reset_input(error=None, source=None, text=None) -> None:
    st.session_state.update(
        input_error=error, source_name=source, report_text=text
    )


def go_to_analysis() -> None:
    st.session_state.nav = "Analyze Report"


# --------------------------------------------------------------------------- #
# Sidebar navigation
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown(f"### {config.APP_NAME}")
    st.caption("AI-powered blood test report analysis")
    st.radio("Navigation", ["Home", "Analyze Report"], key="nav")
    st.divider()
    if config.api_key_available():
        st.caption(f"Model: {config.GEMINI_MODEL}")
    else:
        st.warning("Gemini API key not configured — see the Analyze page.")
    st.caption(
        "For education only — not medical advice. Reports are processed "
        "in memory and are not stored."
    )


# --------------------------------------------------------------------------- #
# Input handling (upload / paste -> cleaned text + preview)
# --------------------------------------------------------------------------- #
def handle_uploaded_file(uploaded) -> None:
    ok, message = validators.validate_upload(uploaded.name, uploaded.size)
    if not ok:
        reset_input(error=message, source=uploaded.name)
        return

    data = uploaded.getvalue()
    try:
        if uploaded.name.lower().endswith(".pdf"):
            pages = pdf_extractor.extract_pdf_text(data)
            if pdf_extractor.is_probably_scanned(pages):
                reset_input(
                    error=pdf_extractor.OCR_REQUIRED_MESSAGE, source=uploaded.name
                )
                return
            text = text_extractor.clean_report_text(
                pdf_extractor.combine_pages(pages)
            )
        else:
            text = text_extractor.extract_txt_text(data)
    except (pdf_extractor.PDFExtractionError, text_extractor.TextExtractionError) as exc:
        reset_input(error=str(exc), source=uploaded.name)
        return

    ok, message = validators.validate_report_text(text)
    if not ok:
        reset_input(error=message, source=uploaded.name)
        return
    reset_input(source=uploaded.name, text=text)


def handle_pasted_text(pasted: str) -> None:
    ok, message = validators.validate_report_text(pasted)
    if not ok:
        reset_input(error=message, source="Pasted text")
        return
    reset_input(
        source="Pasted text", text=text_extractor.clean_report_text(pasted)
    )


def run_analysis() -> None:
    st.session_state.analysis_error = None
    st.session_state.result = None
    try:
        client = GeminiClient()
        with st.status("Analyzing your report…", expanded=True) as status:
            st.write("1/3 — Extracting structured data with Gemini…")
            report, raw = pipeline.run_extraction(
                client, st.session_state.report_text
            )
            st.write(
                f"2/3 — Checking {len(report.tests)} values against the "
                "report's reference ranges (Python)…"
            )
            analyzed = report_analyzer.analyze_report(report)
            st.write("3/3 — Generating simple explanations with Gemini…")
            explanations = pipeline.run_explanations(client, analyzed)
            status.update(label="Analysis complete", state="complete")
        st.session_state.result = pipeline.PipelineResult(
            report=report,
            analyzed=analyzed,
            explanations=explanations,
            raw_extraction_json=raw,
        )
    except (GeminiClientError, json_parser.JSONParsingError) as exc:
        st.session_state.analysis_error = str(exc)
    except Exception as exc:  # last-resort guard so the UI never crashes blank
        st.session_state.analysis_error = f"Unexpected error: {exc}"


# --------------------------------------------------------------------------- #
# Results rendering
# --------------------------------------------------------------------------- #
def style_status_column(df: pd.DataFrame):
    def paint(status: str) -> str:
        color = helpers.STATUS_COLORS.get(status, "#616161")
        background = helpers.STATUS_BACKGROUNDS.get(status, "#F0F0F0")
        return f"background-color: {background}; color: {color}; font-weight: 700;"

    return df.style.map(paint, subset=["Status"])


def render_summary(analyzed) -> None:
    counts = report_analyzer.summary_counts(analyzed)
    tiles = st.columns(6)
    tiles[0].metric("Tests extracted", counts["total"])
    tiles[1].metric("Normal", counts["normal"])
    tiles[2].metric("High", counts["high"])
    tiles[3].metric("Low", counts["low"])
    tiles[4].metric("Not evaluated", counts["not_evaluated"])
    tiles[5].metric("Needs review", counts["needs_review"])

    # One single-axis bar chart of result counts per status. Identity is
    # carried by the axis labels; the colors are the fixed status colors.
    order = [
        range_checker.STATUS_NORMAL,
        range_checker.STATUS_HIGH,
        range_checker.STATUS_LOW,
        range_checker.STATUS_NOT_EVALUATED,
        range_checker.STATUS_NEEDS_REVIEW,
    ]
    values = [counts["normal"], counts["high"], counts["low"],
              counts["not_evaluated"], counts["needs_review"]]
    labels = [helpers.STATUS_BADGE_LABELS[s] for s in order]
    bar_colors = [helpers.STATUS_COLORS[s] for s in order]

    figure = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker_color=bar_colors,
            text=values,
            textposition="outside",
            hovertemplate="%{x}: %{y} test(s)<extra></extra>",
            width=0.55,
        )
    )
    figure.update_layout(
        title="Result counts by status (counts only — not medical severity)",
        height=340,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Number of tests", rangemode="tozero",
                   gridcolor="#E3EDF5", zerolinecolor="#C9D9E8", dtick=1),
        xaxis=dict(title=None),
        font=dict(color="#33475B"),
    )
    st.plotly_chart(
        figure, use_container_width=True, config={"displayModeBar": False}
    )


def render_results_table(analyzed) -> None:
    df = report_analyzer.results_dataframe(analyzed)
    st.dataframe(
        style_status_column(df), use_container_width=True, hide_index=True
    )
    flagged = [
        a for a in analyzed
        if a.status == range_checker.STATUS_NEEDS_REVIEW
    ]
    for item in flagged:
        st.warning(
            f"**{item.test.test_name}** — {item.check.reason}. "
            "Please have this value reviewed by a professional."
        )


def render_explanation_cards(analyzed, explanations) -> None:
    for item in analyzed:
        test = item.test
        explanation = explanations.get(test.test_name)
        badge = helpers.status_badge_html(item.status)
        parts = [
            '<div class="mre-card">',
            f"<h4>{html.escape(test.test_name)} &nbsp;{badge}</h4>",
            f'<p class="mre-kv"><b>Value:</b> '
            f"{html.escape(report_analyzer.format_value(test))}"
            f"{' ' + html.escape(test.unit) if test.unit else ''}</p>",
            f'<p class="mre-kv"><b>Reference range:</b> '
            f"{html.escape(report_analyzer.format_reference(item))}</p>",
            f'<p class="mre-kv"><b>Why this status:</b> '
            f"{html.escape(item.check.reason)}</p>",
        ]
        if explanation:
            text_bits = []
            if explanation.what_it_measures:
                text_bits.append(html.escape(explanation.what_it_measures))
            if explanation.result_explanation:
                text_bits.append(html.escape(explanation.result_explanation))
            parts.append(f'<div class="mre-exp">{" ".join(text_bits)}</div>')
            follow_up = explanation.doctor_discussion or (
                "Please discuss this result with your healthcare professional."
            )
            if explanation.needs_professional_review or follow_up:
                parts.append(
                    f'<div class="mre-followup">{html.escape(follow_up)}</div>'
                )
        else:
            parts.append(
                '<div class="mre-exp">No explanation was generated for this '
                "test. Please discuss the result with your healthcare "
                "professional.</div>"
            )
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)


def render_downloads(result) -> None:
    payload = report_analyzer.export_payload(
        result.report,
        result.analyzed,
        {name: item.model_dump() for name, item in result.explanations.items()},
    )
    json_text = export_results.build_json_export(payload)
    csv_text = export_results.build_csv_export(result.analyzed)
    pdf_bytes = pdf_report.build_pdf_report(
        result.report, result.analyzed, result.explanations
    )

    col_pdf, col_json, col_csv = st.columns(3)
    col_pdf.download_button(
        "⬇ Analysis summary (PDF)",
        data=pdf_bytes,
        file_name=export_results.timestamped_filename("analysis_summary", "pdf"),
        mime="application/pdf",
        use_container_width=True,
    )
    col_json.download_button(
        "⬇ Structured results (JSON)",
        data=json_text,
        file_name=export_results.timestamped_filename("extracted_results", "json"),
        mime="application/json",
        use_container_width=True,
    )
    col_csv.download_button(
        "⬇ Results table (CSV)",
        data=csv_text,
        file_name=export_results.timestamped_filename("results", "csv"),
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(
        "Downloads include the original reference ranges, the Python-calculated "
        "statuses and the medical disclaimer."
    )


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_home() -> None:
    st.markdown(
        f"""
        <div class="mre-hero">
          <h1>{config.APP_NAME}</h1>
          <p>Upload a blood test report (PDF or TXT) or paste its text. The app
          extracts every test with Gemini, checks each value against the
          reference range printed on <i>your own report</i> using plain Python,
          and explains the results in simple language.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### How it works")
        st.markdown(
            """
            <ol class="mre-steps">
              <li><b>Upload</b> your blood test report — PDF, TXT, or pasted text.</li>
              <li><b>Extraction</b> — Gemini copies each test name, value, unit and
                  reference range into structured JSON (validated with Pydantic).</li>
              <li><b>Range check</b> — deterministic Python code classifies every value
                  as LOW, NORMAL or HIGH against the report's own printed ranges.
                  The AI never decides the status.</li>
              <li><b>Explanations</b> — Gemini explains each result in plain English,
                  without diagnoses or treatment advice.</li>
              <li><b>Download</b> — get the summary as PDF, JSON or CSV.</li>
            </ol>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Upload a report →", type="primary", on_click=go_to_analysis
        )
    with right:
        st.markdown("#### Supported input")
        st.markdown(
            f"""
            <div class="mre-card">
              <p class="mre-kv">• <b>PDF</b> — text-based lab reports (max {config.MAX_FILE_SIZE_MB} MB)</p>
              <p class="mre-kv">• <b>TXT</b> — plain-text reports</p>
              <p class="mre-kv">• <b>Paste</b> — copy the report text directly</p>
              <p class="mre-kv">• Scanned/image PDFs are detected and reported —
                 OCR is not performed.</p>
              <p class="mre-kv">• Sample files are included in
                 <code>sample_reports/</code>.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")
    show_disclaimer()


def page_analyze() -> None:
    st.markdown("### Report Upload")

    if not config.api_key_available():
        st.error(config.API_KEY_SETUP_MESSAGE)

    tab_upload, tab_paste = st.tabs(["Upload a file (PDF / TXT)", "Paste report text"])
    with tab_upload:
        uploaded = st.file_uploader(
            "Blood test report",
            type=["pdf", "txt"],
            help=f"PDF or TXT, up to {config.MAX_FILE_SIZE_MB} MB.",
        )
        if uploaded is not None:
            handle_uploaded_file(uploaded)
            size_kb = uploaded.size / 1024
            st.caption(f"**{uploaded.name}** — {size_kb:,.1f} KB")
    with tab_paste:
        pasted = st.text_area(
            "Paste the full report text here",
            height=220,
            placeholder="e.g.  Hemoglobin   10.5   g/dL   12.0 - 16.0 ...",
        )
        if pasted.strip() and uploaded is None:
            handle_pasted_text(pasted)

    if st.session_state.input_error:
        st.error(st.session_state.input_error)
    elif st.session_state.report_text:
        with st.expander(
            f"Preview extracted text — {st.session_state.source_name}", expanded=False
        ):
            st.text(helpers.preview_text(st.session_state.report_text))

    ready = bool(st.session_state.report_text) and config.api_key_available()
    if st.button("Analyze Report", type="primary", disabled=not ready):
        run_analysis()

    if st.session_state.analysis_error:
        st.error(st.session_state.analysis_error)

    result = st.session_state.result
    if result is None:
        return

    st.divider()
    st.markdown("### Report Analysis")
    info = result.report.patient_info
    bits = []
    if info.patient_name:
        bits.append(f"Patient (as printed): **{info.patient_name}**")
    if info.report_date:
        bits.append(f"Report date (as printed): **{info.report_date}**")
    bits.append(f"Source: **{st.session_state.source_name}**")
    st.markdown(" · ".join(bits))

    if not result.analyzed:
        st.warning(
            "No test results could be extracted from this text. Please check "
            "that it is a blood test report."
        )
        return

    render_summary(result.analyzed)
    render_results_table(result.analyzed)

    st.markdown("### Simple Explanations")
    render_explanation_cards(result.analyzed, result.explanations)

    st.markdown("### Download Report")
    render_downloads(result)

    st.markdown("")
    show_disclaimer()


if st.session_state.nav == "Home":
    page_home()
else:
    page_analyze()
