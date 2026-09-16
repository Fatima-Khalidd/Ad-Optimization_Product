# Stage 5 — PDF Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A downloadable PDF of the approved waste report — cover summary, one section per dimension (chart + segment table), numbered recommendations with their reasons, and a methodology footnote — served from `GET /api/reports/{run_id}/pdf` for approved runs only, with numbers identical to the dashboard's.

**Architecture:** One new module, `backend/app/services/pdf.py`, holds a single public function `build_report_pdf(report: ReportOut, business_name: str) -> bytes`. It is a **pure renderer**: it takes the very same `ReportOut` object the dashboard receives from `GET /api/reports/{run_id}` and formats it — no DB access, no recomputation, no second source of truth for any number. The router adds one route that calls Stage 3's `get_report()` (which already enforces "done + approved, else 404") and wraps the bytes in a `Response`. Layout uses ReportLab's `platypus` flowables; the one chart per dimension is a `reportlab.graphics` `HorizontalBarChart` drawn into the flowable stream — **no matplotlib, no image files, no font files**.

**Tech Stack:** Python 3.11, ReportLab 5 (`platypus` + `graphics`, built-in Helvetica), FastAPI, pytest 9, pypdf 6 (test-only, for text extraction).

**Spec:** `docs/PLAN.md` §6 "Stage 5 — PDF report" (authoritative for the "Done when"), §1 #7 (ReportLab chosen over WeasyPrint), §1 #1 (headline waste is the largest single dimension), §3 (the methodology the footnote must describe), §4/§5 (tenant rules and the route path), §7 #6. Cross-stage contract: `docs/superpowers/plans/INTERFACES.md` — **Stage 5** section (`build_report_pdf`, charts via `reportlab.graphics`, no matplotlib, route + headers) and the **Stage 3** section (`ReportOut`, `get_report`, the reports router).

## Global Constraints

- **Stage 3 must be complete before this stage starts.** This plan consumes `app.schemas.reports.ReportOut` and `app.services.analysis.get_report`, and modifies `app/routers/reports.py`, all of which Stage 3 creates. Nothing here re-declares them.
- **The PDF is served only for runs a client may see.** The route calls `get_report(session, client.id, run_id)` and nothing else: Stage 3's rule is `status == "done"` **AND** `review_status == "approved"`, otherwise **404** — the same 404 for another tenant's run, so IDs can't be probed (`docs/PLAN.md` §4 "Tenant isolation"). The router must **not** re-implement or relax that check.
- **The numbers in the PDF must equal the dashboard's.** Same `ReportOut`, same rounding: PKR amounts as `Rs. 84,000` (thousands separator, no decimals — identical to `formatPKR` in INTERFACES.md Stage 4) and percentages to **1 decimal** (`52.5%`, identical to `formatPct`). `build_report_pdf` never re-derives a figure it was handed.
- **Headline waste is the largest single-dimension total, never the sum across dimensions** (`docs/PLAN.md` §1 #1). The methodology footnote must say so in those words.
- **Charts come from `reportlab.graphics.charts.barcharts.HorizontalBarChart`.** No matplotlib anywhere in this stage — INTERFACES.md Stage 5 supersedes the "matplotlib PNGs" aside in `docs/PLAN.md` §1 #7 (see Decisions).
- **Fonts: the built-in Helvetica / Helvetica-Bold only.** No TTF is registered and no font file ships with the app, so nothing can go missing on a deploy host.
- **Layout flowables come from `platypus`:** `SimpleDocTemplate`, `Paragraph`, `Table`, `Spacer`, `KeepTogether`.
- Colours are the frontend's design tokens, read from `frontend/src/app/globals.css`: ink `#0b1220`, teal `#2dd4bf`, coral `#ff6b4a`, paper `#f4f6f8`, slate `#8891a5`. Flagged rows are tinted with coral `#FF6B4A`.
- ruff: `line-length = 100`, rules `E,F,I,B,UP` (`backend/pyproject.toml`). Run `ruff check` **and** `ruff format` before every commit.
- All commands are Windows Git Bash from the repo root, using the venv interpreter directly: `backend/.venv/Scripts/python`, `backend/.venv/Scripts/ruff`.
- Every commit carries the project trailer as a second `-m`: `-m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"`.
- **Frontend: nothing new in this stage.** Stage 4 already renders the download button on `/dashboard/reports/[runId]` pointing at `/api/reports/{runId}/pdf`; the Next.js rewrite proxies it. Task 5 verifies the link exists and stops there.

---

## File Structure

```
backend/
├── requirements.txt                    # MODIFY: + reportlab (runtime dependency)
├── requirements-dev.txt                # MODIFY: + pypdf (tests only — text extraction)
├── app/
│   ├── services/pdf.py                 # CREATE: the whole renderer. One public function.
│   └── routers/reports.py              # MODIFY (Stage 3 file): + GET /{run_id}/pdf
└── tests/
    ├── pdf_utils.py                    # CREATE: pdf_text(bytes) -> str, shared by both test files
    ├── services/
    │   ├── conftest.py                 # CREATE: make_segment / make_dimension / make_report factories
    │   └── test_pdf.py                 # CREATE: renderer tests (text extraction, page count)
    └── api/
        ├── helpers.py                  # MODIFY (Stage 2 created it): + make_approved_run
        └── test_reports_pdf.py         # CREATE: endpoint, headers, 404 pending, 404 cross-tenant
```

Why this split: `pdf.py` is the only file that knows what a report *looks like*; the router keeps knowing only about HTTP and tenancy; the `ReportOut` factories live in `tests/services/conftest.py` so every renderer test builds its input the same way, and the DB-row builders live in `tests/api/helpers.py` — the one shared builder module named by `INTERFACES.md` §"Test-fixture contract" — because only the endpoint tests need rows.

**Reading order for the implementer:** `docs/superpowers/plans/INTERFACES.md` (Stage 3 block — the exact `ReportOut` field names you will render; Stage 5 block — the signature you must produce), then `docs/PLAN.md` §3 (what the numbers mean) and §6 Stage 5.

**Note on test imports:** test modules import shared helpers as `from tests.pdf_utils import pdf_text` and `from tests.api.helpers import make_approved_run`. This resolves because every command below runs `.venv/Scripts/python -m pytest` from `backend/`, which puts `backend/` on `sys.path` (that is also why `import app...` works), and `tests/` resolves as an implicit namespace package. Stage 2 added `tests/api/__init__.py`, and these imports keep working with it.

---

### Task 1: Dependency, report fixtures, and the cover block

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`
- Create: `backend/app/services/pdf.py`
- Create: `backend/tests/pdf_utils.py`
- Create: `backend/tests/services/conftest.py`
- Test: `backend/tests/services/test_pdf.py`

**Interfaces:**
- Consumes (all from Stage 3, `backend/app/schemas/reports.py`):
  ```python
  ReportOut(run_id: int, upload_id: int, generated_at: datetime, date_range_start: date | None,
            date_range_end: date | None, total_spend: float, headline_waste: float,
            recovery_pct: float, dimensions: list[DimensionOut],
            recommendations: list[RecommendationOut], config_snapshot: dict)
  DimensionOut(dimension: str, benchmark_cpa: float | None, total_spend: float,
               total_wasted_spend: float, segments: list[SegmentOut])
  SegmentOut(segment, spend, impressions, clicks, conversions, revenue, cpa, ctr, cvr, roas,
             is_significant, is_flagged, wasted_spend, flag_reason)
  RecommendationOut(id: int, dimension: str, segment_name: str, current_spend: float,
                    recommended_cut: float, reason: str)
  ```
- Produces:
  ```python
  # backend/app/services/pdf.py
  build_report_pdf(report: ReportOut, business_name: str) -> bytes   # a complete, valid PDF
  format_pkr(amount: float | None) -> str    # 84000.0 -> "Rs. 84,000" ; None -> "—"
  format_pct(value: float | None) -> str     # 52.527  -> "52.5%"      ; None -> "—"
  # backend/tests/pdf_utils.py
  pdf_text(data: bytes) -> str               # all pages, whitespace collapsed to single spaces
  pdf_page_count(data: bytes) -> int
  pdf_page_texts(data: bytes) -> list[str]
  # backend/tests/services/conftest.py  (pytest fixtures returning callables)
  make_segment(segment, spend, conversions, **kw) -> SegmentOut
  make_dimension(dimension, segments, **kw) -> DimensionOut
  make_report(**overrides) -> ReportOut        ; sample_report -> ReportOut
  ```

**The fixture numbers (used by every task in this plan).** They are the Stage 1 Task 4 optimizer numbers, extended so the fixture is internally consistent with its own `config_snapshot`:

| Dimension | Segment | spend | clicks | conv | CPA | significant | flagged | wasted |
|---|---|---|---|---|---|---|---|---|
| placement (benchmark **800**) | audience_network | 84,000 | 12,000 | 40 | 2,100 | yes | yes | **52,000** |
| placement | reels | 1,000 | 300 | 0 | — | yes | yes (zero conv) | 1,000 |
| placement | facebook_feed | 15,000 | 4,000 | 30 | 500 | yes | no | 0 |
| placement | messenger_inbox | 900 | 20 | 1 | 900 | **no** | no | 0 |
| age_group (benchmark 800) | 25-34 | 64,900 | 18,000 | 100 | 649 | yes | no | 0 |
| age_group | 35-44 | 16,000 | 5,000 | 25 | 640 | yes | no | 0 |
| age_group | 55-64 | 20,000 | 2,000 | 5 | 4,000 | yes | yes | 16,000 |
| time_slot | *(no rows in the export)* | — | — | — | — | — | — | — |

Totals: placement spend 100,900 / wasted **53,000**; age_group spend 100,900 / wasted 16,000; time_slot 0 / 0.
Report: `total_spend = 100900.0`, `headline_waste = 53000.0` (the max, **not** 53,000 + 16,000), `recovery_pct = 53000/100900*100 = 52.527…` → renders `52.5%`.
`config_snapshot = {"benchmark_mode": "account_avg", "waste_multiplier": 1.5, "min_spend": 1000.0, "min_clicks": 100, "min_spend_zero_conv": 1000.0, "max_cut_pct": 0.6}` — under which every flag above is exactly what `analyzer.py` would produce.

- [ ] **Step 1: Pin the two dependencies**

Run: `backend/.venv/Scripts/python -m pip index versions reportlab` and `backend/.venv/Scripts/python -m pip index versions pypdf`
Expected: a first line like `reportlab (5.0.1)` / `pypdf (6.18.1)`. **Pin the exact latest version each command prints** — if it differs from the numbers below, use what the command printed.

Append to `backend/requirements.txt`:
```text
reportlab==5.0.1
```
Append to `backend/requirements-dev.txt`:
```text
pypdf==6.18.1
```
Run: `backend/.venv/Scripts/python -m pip install -r backend/requirements-dev.txt`
Expected: `Successfully installed pypdf-6.18.1 reportlab-5.0.1` (or "Requirement already satisfied" lines plus those two).

Run: `backend/.venv/Scripts/python -c "import reportlab, pypdf; print(reportlab.Version, pypdf.__version__)"`
Expected: `5.0.1 6.18.1`

- [ ] **Step 2: Write the shared test helpers (no assertions here yet)**

`backend/tests/pdf_utils.py`:
```python
"""Read a generated PDF back as text, so tests can assert on what a client would actually see."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader


def pdf_text(data: bytes) -> str:
    """All pages' text with every run of whitespace collapsed to one space.

    Collapsing matters: ReportLab wraps paragraphs, so a sentence can be split across lines in
    the PDF's text stream. Tests assert on the collapsed string, never on raw extraction.
    """
    reader = PdfReader(BytesIO(data))
    raw = " ".join(page.extract_text() or "" for page in reader.pages)
    return " ".join(raw.split())


def pdf_page_count(data: bytes) -> int:
    return len(PdfReader(BytesIO(data)).pages)


def pdf_page_texts(data: bytes) -> list[str]:
    """Per-page collapsed text — used to prove a long table repeats its header row."""
    reader = PdfReader(BytesIO(data))
    return [" ".join((page.extract_text() or "").split()) for page in reader.pages]
```

`backend/tests/services/conftest.py`:
```python
"""Hand-built ReportOut fixtures with known numbers (see the table in the Stage 5 plan).

The renderer must never recompute anything, so these objects are written out literally rather
than produced by the pipeline: if pdf.py and the dashboard disagree, these numbers say who is
wrong.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.schemas.reports import DimensionOut, RecommendationOut, ReportOut, SegmentOut

TOTAL_SPEND = 100900.0
HEADLINE_WASTE = 53000.0
RECOVERY_PCT = HEADLINE_WASTE / TOTAL_SPEND * 100  # 52.527... -> "52.5%"

CONFIG_SNAPSHOT = {
    "benchmark_mode": "account_avg",
    "waste_multiplier": 1.5,
    "min_spend": 1000.0,
    "min_clicks": 100,
    "min_spend_zero_conv": 1000.0,
    "max_cut_pct": 0.6,
}

AUDIENCE_NETWORK_REASON = (
    "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — "
    "2.6× your placement average of Rs. 800. Cut Rs. 50,400 (60%)."
)
AGE_55_64_REASON = (
    "55-64 spent Rs. 20,000 at Rs. 4,000 per conversion — "
    "5.0× your age group average of Rs. 800. Cut Rs. 12,000 (60%)."
)
REELS_REASON = "Reels spent Rs. 1,000 with no conversions at all. Cut Rs. 600 (60%)."


@pytest.fixture
def make_segment():
    def _make(segment: str, spend: float, conversions: float, **kw) -> SegmentOut:
        clicks = kw.pop("clicks", 1000)
        impressions = kw.pop("impressions", clicks * 50)
        data = dict(
            segment=segment,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            revenue=kw.pop("revenue", 0.0),
            cpa=kw.pop("cpa", spend / conversions if conversions else None),
            ctr=clicks / impressions * 100 if impressions else 0.0,
            cvr=conversions / clicks * 100 if clicks else 0.0,
            roas=None,
            is_significant=kw.pop("is_significant", True),
            is_flagged=kw.pop("is_flagged", False),
            wasted_spend=kw.pop("wasted_spend", 0.0),
            flag_reason=kw.pop("flag_reason", None),
        )
        data.update(kw)
        return SegmentOut(**data)

    return _make


@pytest.fixture
def make_dimension():
    def _make(dimension: str, segments: list[SegmentOut], **kw) -> DimensionOut:
        return DimensionOut(
            dimension=dimension,
            benchmark_cpa=kw.pop("benchmark_cpa", 800.0),
            total_spend=kw.pop("total_spend", sum(s.spend for s in segments)),
            total_wasted_spend=kw.pop("total_wasted_spend", sum(s.wasted_spend for s in segments)),
            segments=segments,
        )

    return _make


@pytest.fixture
def make_report(make_segment, make_dimension):
    def _make(**overrides) -> ReportOut:
        placement = make_dimension(
            "placement",
            [
                make_segment(
                    "audience_network", 84000.0, 40, clicks=12000, revenue=60000.0, cpa=2100.0,
                    is_flagged=True, wasted_spend=52000.0, flag_reason="high_cpa",
                ),
                make_segment(
                    "reels", 1000.0, 0, clicks=300,
                    is_flagged=True, wasted_spend=1000.0, flag_reason="zero_conversions",
                ),
                make_segment("facebook_feed", 15000.0, 30, clicks=4000, revenue=45000.0),
                make_segment("messenger_inbox", 900.0, 1, clicks=20, is_significant=False),
            ],
        )
        age_group = make_dimension(
            "age_group",
            [
                make_segment("25-34", 64900.0, 100, clicks=18000, revenue=150000.0),
                make_segment("35-44", 16000.0, 25, clicks=5000, revenue=40000.0),
                make_segment(
                    "55-64", 20000.0, 5, clicks=2000, cpa=4000.0,
                    is_flagged=True, wasted_spend=16000.0, flag_reason="high_cpa",
                ),
            ],
        )
        time_slot = make_dimension(
            "time_slot", [], benchmark_cpa=None, total_spend=0.0, total_wasted_spend=0.0
        )
        data = dict(
            run_id=7,
            upload_id=3,
            generated_at=datetime(2026, 9, 16, 9, 30, tzinfo=timezone.utc),
            date_range_start=date(2026, 8, 1),
            date_range_end=date(2026, 8, 31),
            total_spend=TOTAL_SPEND,
            headline_waste=HEADLINE_WASTE,
            recovery_pct=RECOVERY_PCT,
            dimensions=[placement, age_group, time_slot],
            recommendations=[
                RecommendationOut(
                    id=11, dimension="placement", segment_name="audience_network",
                    current_spend=84000.0, recommended_cut=50400.0,
                    reason=AUDIENCE_NETWORK_REASON,
                ),
                RecommendationOut(
                    id=12, dimension="age_group", segment_name="55-64",
                    current_spend=20000.0, recommended_cut=12000.0, reason=AGE_55_64_REASON,
                ),
                RecommendationOut(
                    id=13, dimension="placement", segment_name="reels",
                    current_spend=1000.0, recommended_cut=600.0, reason=REELS_REASON,
                ),
            ],
            config_snapshot=dict(CONFIG_SNAPSHOT),
        )
        data.update(overrides)
        return ReportOut(**data)

    return _make


@pytest.fixture
def sample_report(make_report):
    return make_report()
```

- [ ] **Step 3: Write the failing test**

`backend/tests/services/test_pdf.py`:
```python
from app.services.pdf import build_report_pdf, format_pct, format_pkr
from tests.pdf_utils import pdf_page_count, pdf_text

BUSINESS = "Karachi Kicks & Co."


def test_format_pkr_matches_the_dashboard_formatter():
    # INTERFACES.md Stage 4: formatPKR(84000) === "Rs. 84,000"
    assert format_pkr(84000.0) == "Rs. 84,000"
    assert format_pkr(1000.0) == "Rs. 1,000"
    assert format_pkr(2100.4) == "Rs. 2,100"
    assert format_pkr(0.0) == "Rs. 0"
    assert format_pkr(None) == "—"


def test_format_pct_uses_one_decimal_like_the_dashboard():
    # INTERFACES.md Stage 4: formatPct(12.4) === "12.4%"
    assert format_pct(52.527254707631316) == "52.5%"
    assert format_pct(12.4) == "12.4%"
    assert format_pct(0.0) == "0.0%"
    assert format_pct(None) == "—"


def test_output_is_a_real_pdf(sample_report):
    data = build_report_pdf(sample_report, BUSINESS)

    assert data[:4] == b"%PDF"
    assert pdf_page_count(data) >= 1


def test_cover_block_carries_the_business_name_and_the_headline_numbers(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert BUSINESS in text             # also proves "&" is XML-escaped, not a broken Paragraph
    assert "Rs. 100,900" in text        # total spend
    assert "Rs. 53,000" in text         # headline waste
    assert "52.5%" in text              # recovery share, one decimal
    assert "01 Aug 2026" in text and "31 Aug 2026" in text
    assert "16 Sep 2026 09:30" in text  # generated_at


def test_cover_survives_a_report_with_no_date_range(make_report):
    report = make_report(date_range_start=None, date_range_end=None)

    text = pdf_text(build_report_pdf(report, BUSINESS))

    assert "Date range not recorded" in text
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.pdf'`

- [ ] **Step 5: Write the implementation**

`backend/app/services/pdf.py`:
```python
"""The client-facing PDF report.

Rules that must not drift (docs/PLAN.md §6 Stage 5, INTERFACES.md Stage 5):
  * This module is a *renderer*. It formats the same ReportOut the dashboard renders and
    recomputes nothing, so the PDF and the screen cannot disagree.
  * Money is "Rs. 84,000" and percentages have one decimal — identical to the frontend's
    formatPKR/formatPct.
  * Charts are reportlab.graphics drawings. No matplotlib, no image files.
  * Text uses the built-in Helvetica faces only, so no font file has to ship.
"""

from __future__ import annotations

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


def format_pkr(amount: float | None) -> str:
    """Rupees exactly as the dashboard writes them: "Rs. 84,000"."""
    if amount is None:
        return DASH
    return f"Rs. {amount:,.0f}"


def format_pct(value: float | None) -> str:
    """Percentages exactly as the dashboard writes them: "52.5%"."""
    if value is None:
        return DASH
    return f"{value:.1f}%"


def _label(value: str) -> str:
    """"audience_network" -> "Audience Network"; "55-64" and "segment_07" keep their digits."""
    words = value.replace("_", " ").split()
    return " ".join(word.title() if word.isalpha() else word for word in words)


def _dimension_title(dimension: str) -> str:
    return DIMENSION_TITLES.get(dimension, _label(dimension))


def _styles() -> dict[str, ParagraphStyle]:
    sheet = getSampleStyleSheet()
    body = ParagraphStyle(
        "pdf_body", parent=sheet["BodyText"], fontName="Helvetica", fontSize=9, leading=13,
        textColor=INK, spaceAfter=0,
    )
    big = ParagraphStyle(
        "pdf_big", parent=body, fontName="Helvetica-Bold", fontSize=18, leading=21
    )
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
        f"{report.date_range_start:%d %b %Y} to {report.date_range_end:%d %b %Y} "
        f"{DASH} {generated}"
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
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py -v`
Expected: `5 passed`

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
Expected: `All checks passed!` then a `N files reformatted, M files left unchanged` line.
```bash
git add backend/requirements.txt backend/requirements-dev.txt backend/app/services/pdf.py backend/tests/pdf_utils.py backend/tests/services/conftest.py backend/tests/services/test_pdf.py
git commit -m "feat(pdf): ReportLab report skeleton with cover summary block" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Per-dimension sections — benchmark, bar chart, segment table

**Files:**
- Modify: `backend/app/services/pdf.py`
- Test: `backend/tests/services/test_pdf.py` (append)

**Interfaces:**
- Consumes: `build_report_pdf`, `format_pkr`, `format_pct`, `_styles`, `_label`, `_dimension_title`, `CONTENT_WIDTH`, `DASH` and the colour constants from Task 1; `DimensionOut` / `SegmentOut` from Stage 3; the `make_report` / `make_dimension` / `make_segment` fixtures and `pdf_text` / `pdf_page_count` / `pdf_page_texts` from Task 1.
- Produces (module-private; Task 3 reaches them only through `build_report_pdf`):
  ```python
  CHART_SEGMENTS: int = 8
  _spend_vs_waste_chart(dimension: DimensionOut) -> Drawing
  _segment_table(dimension: DimensionOut, st) -> tuple[Table, bool]   # (table, has_insignificant_rows)
  _config_number(config: dict, key: str) -> float | None
  _significance_footnote(config: dict) -> str
  _dimension_section(dimension: DimensionOut, config: dict, st) -> list   # list of flowables
  ```

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_pdf.py`:
```python
def test_each_dimension_gets_a_titled_section_with_its_benchmark(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "Placement" in text
    assert "Age group" in text
    assert "Time of day" in text
    assert "Benchmark CPA Rs. 800" in text


def test_segment_table_lists_every_segment_with_its_numbers(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "Audience Network" in text
    assert "Rs. 84,000" in text       # spend, exactly as the dashboard prints it
    assert "Rs. 2,100" in text        # CPA
    assert "Rs. 52,000" in text       # wasted spend
    assert "Facebook Feed" in text
    assert "Messenger Inbox" in text  # shown even though it is not significant
    assert "55-64" in text


def test_not_significant_rows_get_a_footnote_naming_the_thresholds(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "Not significant: under Rs. 1,000 spend or 100 clicks, so never flagged." in text


def test_footnote_is_omitted_when_every_segment_is_significant(
    make_report, make_dimension, make_segment
):
    report = make_report(
        dimensions=[
            make_dimension("placement", [make_segment("facebook_feed", 15000.0, 30, clicks=4000)])
        ]
    )

    text = pdf_text(build_report_pdf(report, BUSINESS))

    assert "Not significant" not in text


def test_a_dimension_with_no_rows_renders_an_explanation_instead_of_a_chart(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "No rows in this export carried a time of day." in text


def test_chart_legend_names_both_series(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "Spend" in text
    assert "Wasted" in text


def test_sixty_segments_still_render_and_repeat_the_table_header(
    make_report, make_dimension, make_segment
):
    segments = [
        make_segment(f"segment_{i:02d}", 1000.0 + i * 10, 2, clicks=200) for i in range(60)
    ]
    report = make_report(dimensions=[make_dimension("placement", segments)])

    data = build_report_pdf(report, BUSINESS)
    pages = pdf_page_texts(data)
    text = pdf_text(data)

    assert pdf_page_count(data) >= 2                                 # 60 rows cannot fit one page
    assert sum("Segment Spend Conversions" in p for p in pages) >= 2  # repeatRows=1 header
    assert "Segment 00" in text and "Segment 59" in text
```

Also extend the import line at the top of the file to:
```python
from tests.pdf_utils import pdf_page_count, pdf_page_texts, pdf_text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py -v`
Expected: the 5 Task 1 tests pass; the 7 new ones FAIL with `AssertionError` (for example `assert 'Audience Network' in '...'`).

- [ ] **Step 3: Add the chart**

First extend the imports at the top of `backend/app/services/pdf.py` — Task 1 imported only what it used, because ruff's `F401` fails on an unused import:
```python
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, Rect, String
```
and add `KeepTogether` to the existing platypus line, which becomes:
```python
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
```

Then add to `backend/app/services/pdf.py`, after `_summary_table`:
```python
CHART_SEGMENTS = 8  # the chart shows the biggest spenders; the table below lists every segment


def _axis_label(value: float) -> str:
    """Keep the value axis narrow: 84000 -> "84k"."""
    if value >= 1000:
        return f"{value / 1000:,.0f}k"
    return f"{value:,.0f}"


def _spend_vs_waste_chart(dimension) -> Drawing:
    """Spend (teal) against wasted spend (coral) for the top segments, biggest at the top."""
    segments = sorted(dimension.segments, key=lambda s: s.spend, reverse=True)[:CHART_SEGMENTS]
    segments.reverse()  # HorizontalBarChart draws the first category at the bottom

    if not segments:
        drawing = Drawing(CONTENT_WIDTH, 24)
        drawing.add(
            String(
                0,
                8,
                "No rows in this export carried a "
                f"{_dimension_title(dimension.dimension).lower()}.",
                fontName="Helvetica",
                fontSize=8,
                fillColor=SLATE,
            )
        )
        return drawing

    height = 46 + 15 * len(segments)
    drawing = Drawing(CONTENT_WIDTH, height)
    chart = HorizontalBarChart()
    chart.x = 108
    chart.y = 26
    chart.width = CONTENT_WIDTH - 128
    chart.height = height - 46
    chart.data = [
        [float(s.spend) for s in segments],
        [float(s.wasted_spend) for s in segments],
    ]
    chart.categoryAxis.categoryNames = [_label(s.segment) for s in segments]
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.boxAnchor = "e"
    chart.categoryAxis.labels.dx = -4
    chart.categoryAxis.strokeColor = HAIRLINE
    chart.valueAxis.valueMin = 0
    peak = max(float(s.spend) for s in segments)
    chart.valueAxis.valueMax = peak * 1.1 if peak > 0 else 1.0
    chart.valueAxis.labelTextFormat = _axis_label
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.strokeColor = HAIRLINE
    chart.bars[0].fillColor = TEAL
    chart.bars[1].fillColor = CORAL
    chart.bars.strokeWidth = 0
    chart.groupSpacing = 5
    chart.barSpacing = 1
    drawing.add(chart)

    legend_y = height - 12
    drawing.add(Rect(chart.x, legend_y, 6, 6, fillColor=TEAL, strokeColor=None))
    drawing.add(
        String(chart.x + 10, legend_y, "Spend", fontName="Helvetica", fontSize=7, fillColor=SLATE)
    )
    drawing.add(Rect(chart.x + 46, legend_y, 6, 6, fillColor=CORAL, strokeColor=None))
    drawing.add(
        String(chart.x + 56, legend_y, "Wasted", fontName="Helvetica", fontSize=7, fillColor=SLATE)
    )
    return drawing
```

- [ ] **Step 4: Add the segment table and the section assembler**

Add to `backend/app/services/pdf.py`, after `_spend_vs_waste_chart`:
```python
TABLE_HEADER = ("Segment", "Spend", "Conversions", "CPA", "Flag", "Wasted")
COLUMN_FRACTIONS = (0.30, 0.15, 0.145, 0.145, 0.115, 0.145)


def _segment_table(dimension, st: dict[str, ParagraphStyle]) -> tuple[Table, bool]:
    """Returns the table and whether any row was marked not significant (drives the footnote)."""
    rows: list[list] = [[Paragraph(f"<b>{h}</b>", st["cell"]) for h in TABLE_HEADER]]
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), PAPER),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (4, 0), (4, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, HAIRLINE),
    ]
    has_insignificant = False

    for index, seg in enumerate(dimension.segments, start=1):
        name = _label(seg.segment)
        if not seg.is_significant:
            name += " †"  # dagger, explained by the footnote under the table
            has_insignificant = True
        rows.append(
            [
                Paragraph(escape(name), st["cell"]),
                format_pkr(seg.spend),
                f"{seg.conversions:,.0f}",
                format_pkr(seg.cpa),
                "Wasteful" if seg.is_flagged else "",
                format_pkr(seg.wasted_spend) if seg.is_flagged else DASH,
            ]
        )
        if seg.is_flagged:
            commands.append(("BACKGROUND", (0, index), (-1, index), CORAL_TINT))
            commands.append(("TEXTCOLOR", (4, index), (4, index), CORAL))
            commands.append(("FONTNAME", (4, index), (4, index), "Helvetica-Bold"))

    widths = [CONTENT_WIDTH * f for f in COLUMN_FRACTIONS]
    table = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle(commands))
    return table, has_insignificant


def _config_number(config: dict, key: str) -> float | None:
    try:
        return float(config[key])
    except (KeyError, TypeError, ValueError):
        return None


def _significance_footnote(config: dict) -> str:
    min_spend = _config_number(config, "min_spend")
    min_clicks = _config_number(config, "min_clicks")
    if min_spend is None or min_clicks is None:
        return (
            "† Not significant: too little spend or too few clicks to judge, "
            "so never flagged."
        )
    return (
        f"† Not significant: under {format_pkr(min_spend)} spend or "
        f"{min_clicks:,.0f} clicks, so never flagged."
    )


def _dimension_section(dimension, config: dict, st: dict[str, ParagraphStyle]) -> list:
    header = [
        Paragraph(_dimension_title(dimension.dimension), st["h2"]),
        Paragraph(
            f"Benchmark CPA {format_pkr(dimension.benchmark_cpa)} | "
            f"spend {format_pkr(dimension.total_spend)} | "
            f"wasted {format_pkr(dimension.total_wasted_spend)}",
            st["meta"],
        ),
        Spacer(1, 3 * mm),
        _spend_vs_waste_chart(dimension),
        Spacer(1, 3 * mm),
    ]
    # The heading, its benchmark line and the chart travel together; the table is allowed to
    # split across pages (a 60-segment dimension would not fit otherwise) and repeats its header.
    flow: list = [KeepTogether(header)]
    if dimension.segments:
        table, has_insignificant = _segment_table(dimension, st)
        flow.append(table)
        if has_insignificant:
            flow.append(Spacer(1, 1.5 * mm))
            flow.append(Paragraph(_significance_footnote(config), st["footnote"]))
    flow.append(Spacer(1, 7 * mm))
    return flow
```

- [ ] **Step 5: Hook the sections into `build_report_pdf`**

In `backend/app/services/pdf.py`, replace the single line `flow: list = _cover(report, business_name, st)` inside `build_report_pdf` with:
```python
    flow: list = _cover(report, business_name, st)
    for dimension in report.dimensions:
        flow.extend(_dimension_section(dimension, report.config_snapshot or {}, st))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py -v`
Expected: `12 passed`

If `test_sixty_segments_still_render_and_repeat_the_table_header` reports one page, check that `repeatRows=1` is set on the `Table` and that the table was **not** wrapped in `KeepTogether` — a `KeepTogether` around 60 rows silently overflows a single page instead of splitting.

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
Expected: `All checks passed!`
```bash
git add backend/app/services/pdf.py backend/tests/services/test_pdf.py
git commit -m "feat(pdf): per-dimension chart and segment table with flagged-row tint" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Recommendations, empty state, and the methodology footnote

**Files:**
- Modify: `backend/app/services/pdf.py`
- Test: `backend/tests/services/test_pdf.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 1 and 2 (`_config_number` in particular); `RecommendationOut` from Stage 3.
- Produces (module-private; reached through `build_report_pdf`):
  ```python
  METHODOLOGY_KEYS: tuple[str, ...] = ("benchmark_mode", "waste_multiplier", "min_spend",
                                       "min_clicks", "min_spend_zero_conv", "max_cut_pct")
  _recommendations(report: ReportOut, st) -> list
  _config_value(config: dict, key: str) -> str
  _methodology(report: ReportOut, st) -> list
  ```

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_pdf.py`:
```python
def test_recommendations_are_numbered_and_carry_their_reason(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "What to do next" in text
    assert "1. Audience Network" in text
    assert "2. 55-64" in text
    assert "3. Reels" in text
    # The reason sentence, verbatim. It is asserted in two halves so that the em dash and the
    # multiplication sign in the middle cannot turn an extraction quirk into a red test.
    assert "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion" in text
    assert "your placement average of Rs. 800. Cut Rs. 50,400 (60%)." in text
    assert "Reels spent Rs. 1,000 with no conversions at all. Cut Rs. 600 (60%)." in text
    assert "recommended cut Rs. 50,400" in text


def test_report_with_nothing_flagged_renders_an_empty_state(
    make_report, make_dimension, make_segment
):
    clean = make_dimension(
        "placement",
        [make_segment("facebook_feed", 15000.0, 30, clicks=4000)],
        total_wasted_spend=0.0,
    )
    report = make_report(
        dimensions=[clean], recommendations=[], headline_waste=0.0, recovery_pct=0.0
    )

    data = build_report_pdf(report, BUSINESS)
    text = pdf_text(data)

    assert data[:4] == b"%PDF"
    assert "No wasteful segments found" in text
    assert "Rs. 0" in text
    assert "0.0%" in text


def test_methodology_footnote_lists_the_config_that_produced_the_numbers(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "How these numbers were produced" in text
    assert "benchmark_mode = account_avg" in text
    assert "waste_multiplier = 1.5" in text
    assert "min_spend = 1,000" in text
    assert "min_clicks = 100" in text
    assert "min_spend_zero_conv = 1,000" in text
    assert "max_cut_pct = 0.6" in text
    assert "largest single dimension" in text
    assert "not the sum" in text


def test_methodology_survives_a_config_snapshot_missing_keys(make_report):
    report = make_report(config_snapshot={"benchmark_mode": "best"})

    text = pdf_text(build_report_pdf(report, BUSINESS))

    assert "benchmark_mode = best" in text
    assert "waste_multiplier = not recorded" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py -v`
Expected: the 12 earlier tests pass; the 4 new ones FAIL with `AssertionError: assert 'What to do next' in '...'`.

- [ ] **Step 3: Write the implementation**

Add to `backend/app/services/pdf.py`, after `_dimension_section`:
```python
METHODOLOGY_KEYS: tuple[str, ...] = (
    "benchmark_mode",
    "waste_multiplier",
    "min_spend",
    "min_clicks",
    "min_spend_zero_conv",
    "max_cut_pct",
)


def _recommendations(report: ReportOut, st: dict[str, ParagraphStyle]) -> list:
    flow: list = [Paragraph("What to do next", st["h2"]), Spacer(1, 3 * mm)]
    if not report.recommendations:
        flow.append(
            Paragraph(
                "No wasteful segments found in this period. Every segment came in at or near "
                "the benchmark cost per conversion, so there is nothing to cut.",
                st["body"],
            )
        )
        flow.append(Spacer(1, 7 * mm))
        return flow

    for number, rec in enumerate(report.recommendations, start=1):
        heading = (
            f"{number}. {_label(rec.segment_name)} "
            f"({_dimension_title(rec.dimension).lower()})"
        )
        block = [
            Paragraph(escape(heading), st["h3"]),
            Paragraph(escape(rec.reason), st["body"]),
            Paragraph(
                f"Current spend {format_pkr(rec.current_spend)} | "
                f"recommended cut {format_pkr(rec.recommended_cut)}",
                st["meta"],
            ),
            Spacer(1, 4 * mm),
        ]
        flow.append(KeepTogether(block))
    return flow


def _config_value(config: dict, key: str) -> str:
    if key not in config or config[key] is None:
        return "not recorded"
    value = config[key]
    number = None if isinstance(value, bool) else _config_number(config, key)
    if number is None:
        return str(value)
    # Whole thresholds read better with separators (1,000); ratios keep their decimals (1.5).
    return f"{number:,.0f}" if number == int(number) else f"{number:g}"


def _methodology(report: ReportOut, st: dict[str, ParagraphStyle]) -> list:
    config = report.config_snapshot or {}
    settings = " | ".join(f"{key} = {_config_value(config, key)}" for key in METHODOLOGY_KEYS)
    return [
        Paragraph("How these numbers were produced", st["h2"]),
        Spacer(1, 2 * mm),
        Paragraph(
            "A segment is judged only when it clears the significance thresholds. It is flagged "
            "when its cost per conversion exceeds waste_multiplier times the benchmark CPA, or "
            "when it has no conversions at all on at least min_spend_zero_conv of spend. Wasted "
            "spend is the segment's spend minus its conversions priced at the benchmark CPA, "
            "floored at zero; a segment with no conversions counts its whole spend.",
            st["footnote"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "Estimated wasted spend on the cover is the largest single dimension, not the sum "
            "across dimensions: the same rupee appears in the placement, age group and "
            "time-of-day breakdowns at once, so adding them would count it three times.",
            st["footnote"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            f"Settings saved with this run (analysis run {report.run_id}): {escape(settings)}",
            st["footnote"],
        ),
    ]
```

- [ ] **Step 4: Hook both sections into `build_report_pdf`**

In `backend/app/services/pdf.py`, extend the body of `build_report_pdf` so its tail reads exactly:
```python
    st = _styles()
    flow: list = _cover(report, business_name, st)
    for dimension in report.dimensions:
        flow.extend(_dimension_section(dimension, report.config_snapshot or {}, st))
    flow.extend(_recommendations(report, st))
    flow.extend(_methodology(report, st))
    doc.build(flow, onFirstPage=_page_furniture, onLaterPages=_page_furniture)
    return buffer.getvalue()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py -v`
Expected: `16 passed`

- [ ] **Step 6: Check the renderer's own coverage (no gate change)**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py --cov=app/services/pdf --cov-report=term-missing`
Expected: `app\services\pdf.py` at **90% or higher**. If a branch is uncovered, add a test for it here rather than lowering anything — the likely gaps are `_date_line`'s missing-range branch and `_significance_footnote`'s fallback.

- [ ] **Step 7: Look at one generated PDF before moving on**

Temporarily add `import pathlib; pathlib.Path("report.pdf").write_bytes(data)` as the last line of `test_output_is_a_real_pdf`, then run:
```bash
cd backend && .venv/Scripts/python -m pytest tests/services/test_pdf.py::test_output_is_a_real_pdf -q
```
Expected: `1 passed`, and `backend/report.pdf` exists. Open it: the cover, three dimension sections with a teal/coral chart each, three numbered recommendations and the footnote must all look right. Then **delete that line and the file** (`rm backend/report.pdf`) — nothing under `backend/` should write files during tests.

- [ ] **Step 8: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
Expected: `All checks passed!`
```bash
git add backend/app/services/pdf.py backend/tests/services/test_pdf.py
git commit -m "feat(pdf): numbered recommendations, empty state and methodology footnote" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: The `GET /api/reports/{run_id}/pdf` endpoint

**Files:**
- Modify: `backend/app/routers/reports.py` (Stage 3 file)
- Modify: `backend/tests/api/helpers.py` (Stage 2 created it; Stage 3 appended to it — **append** again, overwrite nothing)
- Test: `backend/tests/api/test_reports_pdf.py`

**Interfaces:**
- Consumes:
  - `build_report_pdf(report, business_name) -> bytes` (Task 1) and `pdf_text` (Task 1).
  - Stage 3: `get_report(session, client_id, run_id) -> ReportOut` from `app.services.analysis`, the `APIRouter` in `app/routers/reports.py` (prefix `/api/reports`), `get_session` from `app.core.db`, `CurrentClient` from `app.core.deps`.
  - Test fixtures, exactly as `INTERFACES.md` §"Test-fixture contract" defines them and with no redefinition here: **`db`** (a `Session` on the bound in-memory engine), **`api`** (a `TestClient` that is *not* logged in), **`client_a`** / **`client_b`** (two `TestClient`s, each already logged in as its own tenant), and **`client_a_row`** / **`client_b_row`** (the matching `Client` rows). `login_as` and `make_client` already exist in `tests/api/helpers.py`.
- Produces:
  ```python
  # backend/app/routers/reports.py
  GET /api/reports/{run_id}/pdf -> Response(media_type="application/pdf")
  #   Content-Disposition: attachment; filename="ad-waste-report-{run_id}.pdf"
  # backend/tests/api/helpers.py  (appended; nothing existing is touched)
  make_approved_run(db, client, *, with_report=True, status="done",
                    review_status="approved") -> AnalysisRun
  ```
  `with_report`, `status` and `review_status` are keyword-only additions to the contract's
  `make_approved_run(db, client, *, with_report=True)`; this stage declares them because its
  404 tests need a pending run and a failed one.

- [ ] **Step 1: Write the test helpers (no assertions on the feature yet)**

Append to `backend/tests/api/helpers.py`. Stage 2 created the file (`TEST_PASSWORD`,
`login_as`, `user_for`, `make_client`, `make_admin`) and Stage 3 appended `make_upload` and
`make_run`; **keep every one of those and do not redefine any of them** — this stage adds one
builder and one constant. `CONFIG_SNAPSHOT` is already there from Stage 3, so reuse it rather
than writing a second copy. `ruff format` folds the new imports into the file's single import
block.
```python
AUDIENCE_NETWORK_REASON = (
    "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — "
    "2.6× your placement average of Rs. 800. Cut Rs. 50,400 (60%)."
)


def make_approved_run(
    db: Session,
    client: Client,
    *,
    with_report: bool = True,
    status: str = "done",
    review_status: str = "approved",
) -> AnalysisRun:
    """One finished analysis for `client`, carrying the plan's known placement numbers.

    These are the Stage 1 optimizer test numbers: audience_network spends 84,000 at a CPA of
    2,100 against a placement benchmark of 800 and wastes 52,000; reels spends 1,000 with
    zero conversions and wastes all of it; headline waste is 53,000 of 100,900 total spend.

    `with_report=False` stops after the run row, for a caller that only needs an approved run
    to exist; every test in this stage wants the report, so they all take the default.

    ctr/cvr/roas and flag_reason are not columns on segment_metrics (docs/PLAN.md §4) —
    get_report() derives them, so nothing here sets them.
    """
    upload = make_upload(db, client)
    run = AnalysisRun(
        client_id=client.id,
        upload_id=upload.id,
        config_snapshot=dict(CONFIG_SNAPSHOT),
        status=status,
        review_status=review_status,
        headline_waste=Decimal("53000.00"),
    )
    db.add(run)
    db.flush()

    if not with_report:
        db.commit()
        db.refresh(run)
        return run

    report = WasteReport(
        run_id=run.id,
        client_id=client.id,
        upload_id=upload.id,
        dimension="placement",
        total_spend=Decimal("100900.00"),
        total_wasted_spend=Decimal("53000.00"),
        benchmark_cpa=Decimal("800.00"),
        generated_at=datetime(2026, 9, 16, 9, 30, tzinfo=UTC),
    )
    db.add(report)
    db.flush()

    db.add_all(
        [
            SegmentMetric(
                report_id=report.id,
                segment_value="audience_network",
                spend=Decimal("84000.00"),
                impressions=900000,
                clicks=12000,
                conversions=40,
                revenue=Decimal("60000.00"),
                cpa=Decimal("2100.00"),
                is_significant=True,
                is_flagged=True,
                wasted_spend=Decimal("52000.00"),
            ),
            SegmentMetric(
                report_id=report.id,
                segment_value="reels",
                spend=Decimal("1000.00"),
                impressions=20000,
                clicks=300,
                conversions=0,
                revenue=Decimal("0.00"),
                cpa=None,
                is_significant=True,
                is_flagged=True,
                wasted_spend=Decimal("1000.00"),
            ),
            SegmentMetric(
                report_id=report.id,
                segment_value="facebook_feed",
                spend=Decimal("15000.00"),
                impressions=200000,
                clicks=4000,
                conversions=30,
                revenue=Decimal("45000.00"),
                cpa=Decimal("500.00"),
                is_significant=True,
                is_flagged=False,
                wasted_spend=Decimal("0.00"),
            ),
            SegmentMetric(
                report_id=report.id,
                segment_value="messenger_inbox",
                spend=Decimal("900.00"),
                impressions=1000,
                clicks=20,
                conversions=1,
                revenue=Decimal("1200.00"),
                cpa=Decimal("900.00"),
                is_significant=False,
                is_flagged=False,
                wasted_spend=Decimal("0.00"),
            ),
        ]
    )
    db.add(
        Recommendation(
            report_id=report.id,
            dimension="placement",
            segment_name="audience_network",
            current_spend=Decimal("84000.00"),
            recommended_cut=Decimal("50400.00"),
            reason=AUDIENCE_NETWORK_REASON,
        )
    )
    db.commit()
    db.refresh(run)
    return run
```

The only new import this adds to the file is `Recommendation` from `app.models`; `Decimal`,
`datetime`, `UTC`, `Session`, `Client`, `AnalysisRun`, `WasteReport`, `SegmentMetric`,
`CONFIG_SNAPSHOT` and `make_upload` are all already there from Stages 2 and 3.

- [ ] **Step 2: Write the failing endpoint tests**

`backend/tests/api/test_reports_pdf.py`:
```python
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Client
from tests.api.helpers import make_approved_run
from tests.pdf_utils import pdf_text


def test_approved_run_downloads_as_a_pdf(client_a: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row)

    resp = client_a.get(f"/api/reports/{run.id}/pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == (
        f'attachment; filename="ad-waste-report-{run.id}.pdf"'
    )
    assert resp.content[:4] == b"%PDF"


def test_pdf_content_matches_the_stored_numbers(
    client_a: TestClient, db: Session, client_a_row: Client
):
    run = make_approved_run(db, client_a_row)

    text = pdf_text(client_a.get(f"/api/reports/{run.id}/pdf").content)

    assert client_a_row.business_name in text  # "Alpha Traders"
    assert "Rs. 84,000" in text  # audience_network spend
    assert "Rs. 53,000" in text  # headline waste
    assert "Audience Network" in text
    assert "largest single dimension" in text


def test_pending_run_is_404_not_a_pdf(client_a: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row, review_status="pending")

    resp = client_a.get(f"/api/reports/{run.id}/pdf")

    assert resp.status_code == 404
    assert b"%PDF" not in resp.content


def test_failed_run_is_404(client_a: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row, status="failed", review_status="approved")

    assert client_a.get(f"/api/reports/{run.id}/pdf").status_code == 404


def test_another_tenants_run_is_404_not_403(
    client_b: TestClient, db: Session, client_a_row: Client
):
    run = make_approved_run(db, client_a_row)

    resp = client_b.get(f"/api/reports/{run.id}/pdf")

    assert resp.status_code == 404  # 404, never 403: run ids must not be probeable
    assert b"%PDF" not in resp.content


def test_anonymous_request_is_401(api: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row)

    assert api.get(f"/api/reports/{run.id}/pdf").status_code == 401
```

`client_a` and `client_b` are already-logged-in `TestClient`s, so no `login_as` call is needed
here; `client_a_row` is the `Client` row behind `client_a` (requesting it pulls `client_a` in),
and `api` is the anonymous client.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_reports_pdf.py -v`
Expected: FAIL — the tests expecting 200 get `404` from FastAPI's "Not Found" for an unregistered route (`assert 404 == 200`).

- [ ] **Step 4: Add the route**

In `backend/app/routers/reports.py`, add to the imports:
```python
from fastapi import Response

from app.services.pdf import build_report_pdf
```
(keep the file's existing imports; `ruff format` will order them)

Then add this route **after** the existing `GET /{run_id}` route:
```python
@router.get("/{run_id}/pdf")
def report_pdf(
    run_id: int,
    client: CurrentClient,
    session: Session = Depends(get_session),
) -> Response:
    """The dashboard's report as a downloadable PDF.

    get_report() is the only gate: it already 404s unless the run is done AND approved, and for
    another tenant's run. Do not add a second check here — two gates drift apart.
    """
    report = get_report(session, client.id, run_id)
    pdf = build_report_pdf(report, client.business_name)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ad-waste-report-{run_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_reports_pdf.py -v`
Expected: `6 passed`

If an approved run still 404s, the route is being shadowed: check that `/latest` and `/{run_id}` are declared before `/{run_id}/pdf` in the file, and that no route is declared as `/{run_id:path}`.

- [ ] **Step 6: Run the whole suite, lint, commit**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: every test passes, including Stage 3's report tests — proof the new route changed nothing else.

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
Expected: `All checks passed!`
```bash
git add backend/app/routers/reports.py backend/tests/api/helpers.py backend/tests/api/test_reports_pdf.py
git commit -m "feat(reports): serve the PDF report for approved runs only" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Verify the frontend link, document, and close the stage

**Files:**
- Modify: `README.md`
- Verify only (no edit expected): `frontend/src/app/dashboard/reports/[runId]/page.tsx`

**Interfaces:**
- Consumes: the route from Task 4.
- Produces: nothing new in code.

- [ ] **Step 1: Confirm Stage 4 already links the download**

Run: `grep -rn "reports/.*pdf" frontend/src`
Expected: at least one line in the report page (or a component it renders) containing `/api/reports/${runId}/pdf`. Stage 4 shipped the button and the Next.js rewrite proxies `/api/*` to FastAPI, so **no frontend change belongs in this stage**.

If — and only if — the grep returns nothing, Stage 4 left the button out. Add it to the report page header and say so in the commit message:
```tsx
<a
  className="rounded border border-white/15 px-3 py-1.5 text-sm hover:bg-white/5"
  href={`/api/reports/${runId}/pdf`}
>
  Download PDF
</a>
```

- [ ] **Step 2: Document the endpoint in the README**

Append to `README.md` under the API section:
````markdown
### PDF report (Stage 5)

`GET /api/reports/{run_id}/pdf` returns `application/pdf` as an attachment named
`ad-waste-report-{run_id}.pdf`. It renders the same `ReportOut` the dashboard shows — cover
summary, one section per dimension (chart + segment table), numbered recommendations, and a
methodology footnote listing the run's saved config.

It answers **404** unless the run is `status = done` **and** `review_status = approved`, and for
another client's run. Rendering is ReportLab only (built-in Helvetica, `reportlab.graphics`
charts): there are no fonts or image tools to install on a deploy host.
````

- [ ] **Step 3: Run everything one last time**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check . && .venv/Scripts/python -m pytest -q`
Expected: `All checks passed!`, `N files already formatted`, and a green suite that includes the 16 renderer tests and the 6 endpoint tests.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: describe the Stage 5 PDF report endpoint" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Stage 5 exit checklist (from `docs/PLAN.md` §6)

- [ ] **The PDF numbers match the dashboard exactly, and it is tested.** `format_pkr` / `format_pct` are asserted against the `formatPKR` / `formatPct` contract in INTERFACES.md (Task 1 Step 3), and the renderer takes the dashboard's own `ReportOut` without recomputing anything (Tasks 1–3).
- [ ] **It only works for approved runs.** 404 for `review_status = pending`, 404 for `status = failed`, 404 cross-tenant, 401 anonymous (Task 4 Step 2).
- [ ] Cover summary, per-dimension tables, recommendations with reasons, config/benchmark footnote and the date range are all present and asserted (Tasks 1–3).
- [ ] A 60-segment dimension renders across pages with a repeating header, and a report with nothing flagged renders its empty state (Tasks 2–3).
- [ ] `ruff check` clean, full `pytest` green, `app/services/pdf.py` coverage ≥ 90% (Task 3 Step 6, Task 5 Step 3).
- [ ] The owner has opened one generated PDF and looked at it (Task 3 Step 7).

## Decisions

1. **Charts use `reportlab.graphics`, not matplotlib.** `docs/PLAN.md` §1 #7 mentions "charts in the PDF are rendered as matplotlib PNGs" as an aside; INTERFACES.md's Stage 5 block states `reportlab.graphics — no matplotlib`, and INTERFACES.md is the binding cross-stage contract. It is also the better call: no extra heavyweight dependency, no font-cache or headless-backend problems on a deploy host, and vector bars instead of a rasterised PNG. The §1 #7 headline decision (ReportLab over WeasyPrint) is unchanged.
2. **Built-in Helvetica only.** No TTF is registered, so no font file has to ship or be found at runtime. Space Grotesk stays a screen-only typeface.
3. **Flagged rows are tinted `#FFEDE9`** — the coral token `#FF6B4A` at 12% over white — with the "Wasteful" flag cell itself in full `#FF6B4A` bold. Full-strength coral behind black body text is unreadable in print; the tint plus the coloured flag keeps the row obvious.
4. **The chart shows the top 8 segments by spend; the table lists every segment.** A 60-category bar chart is unreadable, and the table is the authoritative list.
5. **`KeepTogether` wraps the dimension heading + benchmark line + chart, never the table.** Wrapping a 60-row table in `KeepTogether` overflows a single page; `repeatRows=1` gives the header on every page instead. Recommendation blocks are each wrapped so a reason never splits from its heading.
6. **Not-significant segments are shown with a dagger and one footnote**, with the thresholds read from `config_snapshot` (`min_spend`, `min_clicks`), so the footnote can never contradict the run that produced it.
7. **The empty state is a sentence, not a hidden section.** A report with nothing flagged still renders every dimension section plus "No wasteful segments found in this period."; a client who paid for an analysis gets a document either way.
8. **The route adds no second approval check.** `get_report()` is the single gate (INTERFACES.md Stage 3), so the approval rule can only ever change in one place.
9. **`Cache-Control: no-store` on the response.** The PDF contains a client's spend data and should not sit in a proxy cache.
10. **All user-supplied text is XML-escaped** (`business_name`, segment names, recommendation reasons) before it reaches a `Paragraph` — an `&` in a business name would otherwise raise a ReportLab parse error at render time. The test business name is `Karachi Kicks & Co.` precisely to keep that path covered.
11. **Test fixture numbers are the Stage 1 Task 4 optimizer numbers** (84,000 spend / 52,000 waste / 800 benchmark / 50,400 cut), extended with a not-significant segment and an empty `time_slot` dimension, and given a `config_snapshot` under which every flag in the fixture is exactly what `analyzer.py` would produce. Dimension totals are the sum of their own segments (100,900), and `headline_waste` is the placement total (53,000), never 53,000 + 16,000.
12. **The reason sentence is asserted in two halves** around the em dash and `×`. Both characters are in WinAnsi and normally extract fine, but splitting the assertion means a pypdf glyph-mapping quirk can never masquerade as a missing recommendation.
13. **Shared test helpers are imported as `tests.pdf_utils` / `tests.api.helpers`**, which resolves because every command runs `python -m pytest` from `backend/`.

## Self-review notes

- **Spec coverage** against `docs/PLAN.md` §6 Stage 5: "cover summary" ✔ Task 1; "per-dimension tables" ✔ Task 2 (plus the chart INTERFACES.md requires); "recommendations with reasons" ✔ Task 3; "config/benchmark footnote" ✔ Task 3 (all six keys named in the brief, plus the benchmark CPA on every dimension heading in Task 2); "the date range" ✔ Task 1 cover line; "PDF numbers match the dashboard exactly (tested)" ✔ Task 1 formatter tests plus renderer purity; "only works for approved runs" ✔ Task 4. §1 #1 headline-waste wording ✔ Task 3 methodology. §1 #7 ReportLab ✔; the matplotlib aside is overridden per Decision 1. §5 route path and §4 tenant-404 rule ✔ Task 4. §7 #6 ✔.
- **Placeholder scan:** no TBD/TODO/"handle edge cases". Every code step carries real code; every command carries its expected output. The only conditional passage is Task 5 Step 1's "if Stage 4 left the button out", which ships the full snippet rather than a description.
- **Type consistency:** `build_report_pdf(report, business_name) -> bytes` is spelled identically in Tasks 1, 4 and INTERFACES.md. `format_pkr` / `format_pct` (Task 1) are used unchanged in Tasks 2–3. `_spend_vs_waste_chart`, `_segment_table`, `_config_number`, `_significance_footnote`, `_dimension_section` (Task 2) are called with the argument order they are defined with; `_config_value` (Task 3) reuses `_config_number` from Task 2 rather than redefining it. `make_segment` / `make_dimension` / `make_report` / `sample_report` (Task 1) keep their signatures in Tasks 2–3. `make_approved_run(db, client, *, with_report, status, review_status)` (Task 4) is called exactly as defined, and is the only name this stage adds to `tests/api/helpers.py`; `db`, `api`, `client_a`, `client_b`, `client_a_row` and `login_as` come from `INTERFACES.md` §"Test-fixture contract" unchanged. `pdf_text` / `pdf_page_count` / `pdf_page_texts` (Task 1) keep those names in Tasks 2–4.
- **Deliberate non-goals:** the invoice PDF is Stage 7's `build_invoice_pdf` and is not generalised here (YAGNI — a shared "PDF theme" module can be extracted then, when there are two callers); no admin-side PDF; no frontend work.
