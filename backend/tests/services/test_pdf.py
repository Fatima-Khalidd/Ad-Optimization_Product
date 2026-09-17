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
