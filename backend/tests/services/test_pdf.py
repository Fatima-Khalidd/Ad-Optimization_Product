from decimal import Decimal

from app.services.pdf import build_report_pdf, format_pct, format_pkr
from tests.pdf_utils import pdf_page_count, pdf_page_texts, pdf_text

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

    assert BUSINESS in text  # also proves "&" is XML-escaped, not a broken Paragraph
    assert "Rs. 100,900" in text  # total spend
    assert "Rs. 53,000" in text  # headline waste
    assert "52.5%" in text  # recovery share, one decimal
    assert "01 Aug 2026" in text and "31 Aug 2026" in text
    assert "16 Sep 2026 09:30" in text  # generated_at


def test_cover_survives_a_report_with_no_date_range(make_report):
    report = make_report(date_range_start=None, date_range_end=None)

    text = pdf_text(build_report_pdf(report, BUSINESS))

    assert "Date range not recorded" in text


def test_each_dimension_gets_a_titled_section_with_its_benchmark(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "Placement" in text
    assert "Age group" in text
    assert "Time of day" in text
    assert "Benchmark CPA Rs. 800" in text


def test_segment_table_lists_every_segment_with_its_numbers(sample_report):
    text = pdf_text(build_report_pdf(sample_report, BUSINESS))

    assert "Audience Network" in text
    assert "Rs. 84,000" in text  # spend, exactly as the dashboard prints it
    assert "Rs. 2,100" in text  # CPA
    assert "Rs. 52,000" in text  # wasted spend
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
    segments = [make_segment(f"segment_{i:02d}", 1000.0 + i * 10, 2, clicks=200) for i in range(60)]
    report = make_report(dimensions=[make_dimension("placement", segments)])

    data = build_report_pdf(report, BUSINESS)
    pages = pdf_page_texts(data)
    text = pdf_text(data)

    assert pdf_page_count(data) >= 2  # 60 rows cannot fit one page
    assert sum("Segment Spend Conversions" in p for p in pages) >= 2  # repeatRows=1 header
    assert "Segment 00" in text and "Segment 59" in text


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


def test_format_pkr_rounds_half_up_like_the_dashboard_not_bankers_rounding():
    # Decimal's default context is ROUND_HALF_EVEN; the dashboard's Math.round is half-away-
    # from-zero. These exact-half cases are where the two disagree, so they pin the behaviour.
    assert format_pkr(Decimal("84000.50")) == "Rs. 84,001"
    assert format_pkr(Decimal("0.50")) == "Rs. 1"


def test_format_pct_rounds_half_up_like_the_dashboard_not_bankers_rounding():
    assert format_pct(Decimal("16.25")) == "16.3%"
    assert format_pct(Decimal("16.35")) == "16.4%"


def test_format_pkr_and_pct_never_print_a_negative_zero():
    assert format_pkr(Decimal("-0.4")) == "Rs. 0"
    assert format_pct(Decimal("-0.04")) == "0.0%"


def test_format_pkr_and_pct_still_dash_on_none():
    assert format_pkr(None) == "—"
    assert format_pct(None) == "—"


def test_headline_waste_on_an_exact_half_rupee_renders_rounded_up(make_report):
    report = make_report(headline_waste=Decimal("210794.50"))

    text = pdf_text(build_report_pdf(report, BUSINESS))

    assert "Rs. 210,795" in text


def test_wasted_column_uses_wasted_spend_not_is_flagged(make_report, make_dimension, make_segment):
    # A segment marked flagged but with zero wasted_spend must show "—" in the Wasted column,
    # matching the dashboard's `Number(wasted_spend) > 0` predicate (SegmentTable.tsx) rather
    # than the PDF's own is_flagged check. The "Wasteful" tag still tracks is_flagged — only
    # the Wasted amount cell's predicate changes.
    odd = make_segment(
        "odd_one", 5000.0, 10, clicks=500, cpa=500.0, is_flagged=True, wasted_spend=0.0
    )
    report = make_report(dimensions=[make_dimension("placement", [odd])])

    text = pdf_text(build_report_pdf(report, BUSINESS))

    assert "Odd One" in text
    assert "Rs. 5,000" in text  # spend still prints
    # The row's own Wasted cell must read "Wasteful —", not "Wasteful Rs. 0" — the dimension
    # header line separately (and legitimately) shows "wasted Rs. 0" as the dimension's total.
    assert "Wasteful —" in text
