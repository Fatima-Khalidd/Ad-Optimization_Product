"""The client-facing PDF report.

Rules that must not drift (docs/PLAN.md §6 Stage 5, INTERFACES.md Stage 5):
  * This module is a *renderer*. It formats the same ReportOut the dashboard renders and
    recomputes nothing, so the PDF and the screen cannot disagree.
  * Money is "Rs. 84,000" and percentages have one decimal — identical to the frontend's
    formatPKR/formatPct. Both take the report's native Decimal fields directly: never round a
    Decimal through a float first, or the PDF can print a different digit than the dashboard.
  * Charts are reportlab.graphics drawings. No matplotlib, no image files.
  * Text uses the built-in Helvetica faces only, so no font file has to ship.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.reports import ReportOut

# Design tokens, copied from frontend/src/app/globals.css so print matches screen.
INK = colors.HexColor("#0B1220")
TEAL = colors.HexColor("#2DD4BF")
CORAL = colors.HexColor("#FF6B4A")
PAPER = colors.HexColor("#F4F6F8")
SLATE = colors.HexColor("#8891A5")
HAIRLINE = colors.HexColor("#E3E7ED")
# #FF6B4A at 12% over white: enough tint to spot a flagged row, still black-text readable.
CORAL_TINT = colors.HexColor("#FFEDE9")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

DASH = "—"  # em dash, used wherever a number is genuinely absent

DIMENSION_TITLES = {
    "placement": "Placement",
    "age_group": "Age group",
    "time_slot": "Time of day",
}


def format_pkr(amount: Decimal | float | None) -> str:
    """Rupees exactly as the dashboard writes them: "Rs. 84,000".

    Formats the Decimal (or float) directly with the standard format mini-language, so a
    Decimal amount is never routed through a float and re-rounded on the way.
    """
    if amount is None:
        return DASH
    return f"Rs. {amount:,.0f}"


def format_pct(value: Decimal | float | None) -> str:
    """Percentages exactly as the dashboard writes them: "52.5%"."""
    if value is None:
        return DASH
    return f"{value:.1f}%"


def _label(value: str) -> str:
    """ "audience_network" -> "Audience Network"; "55-64" and "segment_07" keep their digits."""
    words = value.replace("_", " ").split()
    return " ".join(word.title() if word.isalpha() else word for word in words)


def _dimension_title(dimension: str) -> str:
    return DIMENSION_TITLES.get(dimension, _label(dimension))


def _styles() -> dict[str, ParagraphStyle]:
    sheet = getSampleStyleSheet()
    body = ParagraphStyle(
        "pdf_body",
        parent=sheet["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=INK,
        spaceAfter=0,
    )
    big = ParagraphStyle("pdf_big", parent=body, fontName="Helvetica-Bold", fontSize=18, leading=21)
    return {
        "title": ParagraphStyle(
            "pdf_title", parent=body, fontName="Helvetica-Bold", fontSize=20, leading=24
        ),
        "subtitle": ParagraphStyle(
            "pdf_subtitle", parent=body, fontName="Helvetica-Bold", fontSize=13, leading=17
        ),
        "h2": ParagraphStyle(
            "pdf_h2", parent=body, fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=2
        ),
        "h3": ParagraphStyle(
            "pdf_h3", parent=body, fontName="Helvetica-Bold", fontSize=9.5, leading=13
        ),
        "body": body,
        "meta": ParagraphStyle("pdf_meta", parent=body, fontSize=8, leading=11, textColor=SLATE),
        "cell": ParagraphStyle("pdf_cell", parent=body, fontSize=8, leading=10),
        "footnote": ParagraphStyle(
            "pdf_footnote", parent=body, fontSize=7.5, leading=10, textColor=SLATE
        ),
        "big": big,
        "big_coral": ParagraphStyle("pdf_big_coral", parent=big, textColor=CORAL),
        "big_teal": ParagraphStyle("pdf_big_teal", parent=big, textColor=TEAL),
    }


def _summary_table(report: ReportOut, st: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [
            Paragraph(format_pkr(report.total_spend), st["big"]),
            Paragraph(format_pkr(report.headline_waste), st["big_coral"]),
            Paragraph(format_pct(report.recovery_pct), st["big_teal"]),
        ],
        [
            Paragraph("Total spend", st["meta"]),
            Paragraph("Estimated wasted spend", st["meta"]),
            Paragraph("Recoverable share", st["meta"]),
        ],
    ]
    column = CONTENT_WIDTH / 3.0
    table = Table(rows, colWidths=[column, column, column], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, HAIRLINE),
            ]
        )
    )
    return table


def _date_line(report: ReportOut) -> str:
    generated = f"generated {report.generated_at:%d %b %Y %H:%M} UTC"
    if report.date_range_start is None or report.date_range_end is None:
        return f"Date range not recorded {DASH} {generated}"
    return (
        f"{report.date_range_start:%d %b %Y} to {report.date_range_end:%d %b %Y} {DASH} {generated}"
    )


def _cover(report: ReportOut, business_name: str, st: dict[str, ParagraphStyle]) -> list:
    return [
        Paragraph("Ad spend waste report", st["title"]),
        Paragraph(escape(business_name), st["subtitle"]),
        Paragraph(escape(_date_line(report)), st["meta"]),
        Spacer(1, 7 * mm),
        _summary_table(report, st),
        Spacer(1, 3 * mm),
        Paragraph(
            "Estimated wasted spend is the largest single dimension below, not the sum of them.",
            st["meta"],
        ),
        Spacer(1, 7 * mm),
    ]


def _page_furniture(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE)
    canvas.drawString(MARGIN, 11 * mm, "Ad Spend Optimization")
    canvas.drawRightString(PAGE_WIDTH - MARGIN, 11 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(HAIRLINE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 14 * mm, PAGE_WIDTH - MARGIN, 14 * mm)
    canvas.restoreState()


def build_report_pdf(report: ReportOut, business_name: str) -> bytes:
    """Render an approved report as PDF bytes. Pure: no DB, no I/O beyond the in-memory buffer."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=20 * mm,
        title=f"Ad spend waste report {DASH} {business_name}",
        author="Ad Spend Optimization",
        subject=f"Analysis run {report.run_id}",
    )
    st = _styles()
    flow: list = _cover(report, business_name, st)
    doc.build(flow, onFirstPage=_page_furniture, onLaterPages=_page_furniture)
    return buffer.getvalue()
