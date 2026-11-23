"""Builds the downloadable PDF analysis summary (A4, reportlab/platypus).

The PDF contains the extracted results with their ORIGINAL reference ranges,
the Python-calculated statuses, the LLM's simple explanations, and the
medical disclaimer (prominently at the top and again at the end).
Everything is produced in memory — nothing is written to disk.
"""

from io import BytesIO
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import config
from analysis.report_analyzer import (
    AnalyzedTest,
    format_reference,
    format_value,
    summary_counts,
)
from extraction.models import ExtractedReport
from utils.helpers import STATUS_BACKGROUNDS, STATUS_COLORS, now_display

_PAGE_WIDTH = A4[0] - 4 * cm  # usable width with 2 cm margins


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "RTitle", parent=base["Title"], fontSize=18, spaceAfter=4,
            textColor=colors.HexColor("#0D47A1"),
        ),
        "subtitle": ParagraphStyle(
            "RSub", parent=base["Normal"], fontSize=9.5, alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"), spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "RH2", parent=base["Heading2"], fontSize=13, spaceBefore=12,
            spaceAfter=6, textColor=colors.HexColor("#0D47A1"),
        ),
        "body": ParagraphStyle(
            "RBody", parent=base["Normal"], fontSize=10, leading=13.5,
        ),
        "cell": ParagraphStyle("RCell", parent=base["Normal"], fontSize=9, leading=11.5),
        "disclaimer": ParagraphStyle(
            "RDisc", parent=base["Normal"], fontSize=8.5, leading=11,
            textColor=colors.HexColor("#7A4E00"),
        ),
    }


def _disclaimer_box(styles) -> Table:
    box = Table(
        [[Paragraph(config.DISCLAIMER, styles["disclaimer"])]],
        colWidths=[_PAGE_WIDTH],
    )
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF8E7")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E0A800")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return box


def _results_table(analyzed_tests: List[AnalyzedTest], styles) -> Table:
    header = ["Test", "Value", "Unit", "Reference Range", "Status"]
    rows = [header]
    for analyzed in analyzed_tests:
        test = analyzed.test
        rows.append(
            [
                Paragraph(test.test_name, styles["cell"]),
                Paragraph(format_value(test), styles["cell"]),
                Paragraph(test.unit or "—", styles["cell"]),
                Paragraph(format_reference(analyzed), styles["cell"]),
                Paragraph(analyzed.status, styles["cell"]),
            ]
        )

    table = Table(
        rows,
        colWidths=[4.2 * cm, 2.2 * cm, 2.0 * cm, 5.0 * cm, 3.6 * cm],
        repeatRows=1,
    )
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D47A1")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B0BEC5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    # Colour each status cell according to the calculated status.
    for row_index, analyzed in enumerate(analyzed_tests, start=1):
        background = STATUS_BACKGROUNDS.get(analyzed.status)
        foreground = STATUS_COLORS.get(analyzed.status)
        if background:
            style.append(
                ("BACKGROUND", (4, row_index), (4, row_index), colors.HexColor(background))
            )
        if foreground:
            style.append(
                ("TEXTCOLOR", (4, row_index), (4, row_index), colors.HexColor(foreground))
            )
    table.setStyle(TableStyle(style))
    return table


def build_pdf_report(
    report: ExtractedReport,
    analyzed_tests: List[AnalyzedTest],
    explanations: Dict[str, object],
) -> bytes:
    """Render the analysis summary PDF and return it as bytes."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"{config.APP_NAME} — Analysis Summary",
    )
    styles = _styles()
    story = []

    story.append(Paragraph(config.APP_NAME, styles["title"]))
    story.append(
        Paragraph(
            f"AI-assisted blood test report analysis — generated {now_display()}",
            styles["subtitle"],
        )
    )
    story.append(_disclaimer_box(styles))
    story.append(Spacer(1, 10))

    info = report.patient_info
    meta_bits = []
    if info.patient_name:
        meta_bits.append(f"<b>Patient (as printed):</b> {info.patient_name}")
    if info.report_date:
        meta_bits.append(f"<b>Report date (as printed):</b> {info.report_date}")
    if meta_bits:
        story.append(Paragraph(" &nbsp;&nbsp; ".join(meta_bits), styles["body"]))
        story.append(Spacer(1, 6))

    counts = summary_counts(analyzed_tests)
    story.append(
        Paragraph(
            f"<b>Summary:</b> {counts['total']} tests extracted — "
            f"{counts['normal']} normal, {counts['high']} high, "
            f"{counts['low']} low, {counts['not_evaluated']} not evaluated, "
            f"{counts['needs_review']} needing review.",
            styles["body"],
        )
    )

    story.append(Paragraph("Results", styles["h2"]))
    story.append(_results_table(analyzed_tests, styles))

    if explanations:
        story.append(Paragraph("Simple Explanations", styles["h2"]))
        for analyzed in analyzed_tests:
            item = explanations.get(analyzed.test.test_name)
            if item is None:
                continue
            story.append(
                Paragraph(
                    f"<b>{analyzed.test.test_name}</b> — "
                    f"value {format_value(analyzed.test)}"
                    f"{' ' + analyzed.test.unit if analyzed.test.unit else ''}, "
                    f"reference {format_reference(analyzed)}, "
                    f"status <b>{analyzed.status}</b>",
                    styles["body"],
                )
            )
            pieces = []
            if item.what_it_measures:
                pieces.append(item.what_it_measures)
            if item.result_explanation:
                pieces.append(item.result_explanation)
            if item.doctor_discussion:
                pieces.append(item.doctor_discussion)
            story.append(Paragraph(" ".join(pieces), styles["body"]))
            if item.needs_professional_review:
                story.append(
                    Paragraph(
                        "<i>This result should be reviewed with a healthcare "
                        "professional.</i>",
                        styles["body"],
                    )
                )
            story.append(Spacer(1, 8))

    story.append(Spacer(1, 10))
    story.append(_disclaimer_box(styles))

    document.build(story)
    return buffer.getvalue()
