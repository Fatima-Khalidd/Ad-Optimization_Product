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
