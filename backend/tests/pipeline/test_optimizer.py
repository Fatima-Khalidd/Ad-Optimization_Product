from decimal import Decimal

import pytest

from app.pipeline.analyzer import DimensionResult, SegmentMetrics
from app.pipeline.config import PipelineConfig
from app.pipeline.optimizer import build_recommendations, calculate_fee, headline_waste


def _seg(name, spend, conv, wasted, reason):
    return SegmentMetrics(
        segment=name,
        spend=spend,
        impressions=1000,
        clicks=100,
        conversions=conv,
        revenue=0.0,
        cpa=(spend / conv if conv else None),
        ctr=0.1,
        cvr=0.0,
        roas=None,
        is_significant=True,
        is_flagged=reason is not None,
        wasted_spend=wasted,
        flag_reason=reason,
    )


def _results():
    placement = DimensionResult(
        dimension="placement",
        benchmark_cpa=800.0,
        total_spend=100000.0,
        total_wasted_spend=53000.0,
        segments=[
            _seg("audience_network", 84000.0, 40, 52000.0, "high_cpa"),  # cpa 2100
            _seg("reels", 1000.0, 0, 1000.0, "zero_conversions"),
            _seg("feed", 15000.0, 30, 0.0, None),
        ],
    )
    age = DimensionResult(
        dimension="age_group",
        benchmark_cpa=800.0,
        total_spend=100000.0,
        total_wasted_spend=12000.0,
        segments=[_seg("55-64", 20000.0, 5, 12000.0, "high_cpa")],
    )
    time_slot = DimensionResult(
        dimension="time_slot",
        benchmark_cpa=None,
        total_spend=0.0,
        total_wasted_spend=0.0,
        segments=[],
    )
    return {"placement": placement, "age_group": age, "time_slot": time_slot}


def test_headline_waste_is_max_not_sum():
    assert headline_waste(_results()) == 53000.0


def test_headline_waste_is_zero_when_nothing_flagged():
    assert headline_waste({"time_slot": _results()["time_slot"]}) == 0.0


def test_recommendations_cap_cut_at_max_cut_pct_and_sort_by_cut():
    cfg = PipelineConfig.from_overrides({"max_cut_pct": 0.6})

    recs = build_recommendations(_results(), cfg)

    assert [(r.dimension, r.segment_name) for r in recs] == [
        ("placement", "audience_network"),
        ("age_group", "55-64"),
        ("placement", "reels"),
    ]
    an = recs[0]
    assert an.current_spend == 84000.0
    assert an.recommended_cut == pytest.approx(50400.0)  # min(52000, 0.6*84000)
    assert recs[2].recommended_cut == pytest.approx(600.0)  # min(1000, 0.6*1000)


def test_high_cpa_reason_reads_in_plain_language_with_real_numbers():
    rec = build_recommendations(_results(), PipelineConfig())[0]

    assert rec.reason == (
        "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — "
        "2.6× your placement average of Rs. 800. Cut Rs. 50,400 (60%)."
    )


def test_zero_conversion_reason():
    rec = [
        r for r in build_recommendations(_results(), PipelineConfig()) if r.segment_name == "reels"
    ][0]

    assert rec.reason == "Reels spent Rs. 1,000 with no conversions at all. Cut Rs. 600 (60%)."


def test_fee_uses_decimal_and_rounds_half_up():
    fee = calculate_fee(Decimal("15000"), Decimal("20"), Decimal("12345.675"))

    assert fee.performance_fee == Decimal("2469.14")  # 2469.135 -> half up
    assert fee.total == Decimal("17469.14")
    assert fee.base_fee == Decimal("15000.00")
    assert fee.cap_applied is False
    assert isinstance(fee.total, Decimal)


def test_fee_cap_limits_performance_fee():
    fee = calculate_fee(Decimal("15000"), Decimal("20"), Decimal("500000"), cap=Decimal("40000"))

    assert fee.performance_fee == Decimal("40000.00")
    assert fee.cap_applied is True
    assert fee.total == Decimal("55000.00")


def test_fee_zero_recovered_waste_is_just_base_fee():
    fee = calculate_fee(Decimal("15000"), Decimal("20"), Decimal("0"))
    assert fee.performance_fee == Decimal("0.00")
    assert fee.total == Decimal("15000.00")


@pytest.mark.parametrize(
    "base, pct, waste",
    [
        (Decimal("-1"), Decimal("20"), Decimal("0")),
        (Decimal("1"), Decimal("120"), Decimal("0")),
        (Decimal("1"), Decimal("20"), Decimal("-5")),
    ],
)
def test_fee_rejects_negative_or_out_of_range_inputs(base, pct, waste):
    with pytest.raises(ValueError):
        calculate_fee(base, pct, waste)


def test_fee_rejects_negative_cap():
    with pytest.raises(ValueError):
        calculate_fee(15000, 20, 1000, cap=Decimal("-500"))


def test_fee_zero_cap_zeroes_performance_fee():
    fee = calculate_fee(Decimal("15000"), Decimal("20"), Decimal("23000"), cap=Decimal("0"))

    assert fee.performance_fee == Decimal("0.00")
    assert fee.total == Decimal("15000.00")
    assert fee.cap_applied is True


def test_fee_rejects_non_numeric_input():
    with pytest.raises(ValueError):
        calculate_fee("abc", 20, 1000)


@pytest.mark.parametrize(
    "value",
    [float("inf"), float("-inf"), float("nan"), Decimal("Infinity"), Decimal("NaN")],
)
def test_fee_rejects_non_finite_recovered_waste(value):
    with pytest.raises(ValueError):
        calculate_fee(15000, 20, value)
