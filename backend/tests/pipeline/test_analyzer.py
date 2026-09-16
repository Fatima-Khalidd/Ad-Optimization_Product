import pandas as pd
import pytest

from app.pipeline.analyzer import analyze_all_dimensions, analyze_dimension
from app.pipeline.config import PipelineConfig

CFG = PipelineConfig.from_overrides(
    {
        "min_spend": 1000,
        "min_clicks": 10,
        "waste_multiplier": 1.5,
        "min_spend_zero_conv": 500,
        "min_conversions_for_best": 5,
    }
)


def _row(placement, spend, clicks, conv, *, age_group="25-34", time_slot="morning"):
    return {
        "date": pd.Timestamp("2026-08-01"),
        "campaign_id": "c1",
        "placement": placement,
        "age_group": age_group,
        "gender": "male",
        "device": "mobile",
        "time_slot": time_slot,
        "spend": float(spend),
        "impressions": clicks * 20,
        "clicks": clicks,
        "conversions": conv,
        "revenue": conv * 2500.0,
    }


def _base_df():
    return pd.DataFrame(
        [
            _row("feed", 10000, 500, 20),
            _row("stories", 6000, 300, 10),
            _row("audience_network", 8000, 400, 4),
            _row("tiny", 200, 5, 0),
        ]
    )


def _by_segment(result):
    return {s.segment: s for s in result.segments}


def test_account_avg_benchmark_flags_only_the_expensive_segment():
    result = analyze_dimension(_base_df(), "placement", CFG)

    assert result.benchmark_cpa == pytest.approx(705.88, abs=0.01)
    assert result.total_spend == pytest.approx(24200)
    seg = _by_segment(result)
    assert [s.segment for s in result.flagged] == ["audience_network"]
    assert seg["audience_network"].flag_reason == "high_cpa"
    assert seg["audience_network"].wasted_spend == pytest.approx(5176.47, abs=0.01)
    assert result.total_wasted_spend == pytest.approx(5176.47, abs=0.01)
    assert seg["feed"].wasted_spend == 0
    assert seg["feed"].cpa == 500


def test_insignificant_segment_is_reported_but_never_flagged():
    seg = _by_segment(analyze_dimension(_base_df(), "placement", CFG))

    assert seg["tiny"].is_significant is False
    assert seg["tiny"].is_flagged is False
    assert seg["tiny"].cpa is None  # zero conversions


def test_zero_conversion_segment_is_flagged_with_full_spend_as_waste():
    df = pd.concat([_base_df(), pd.DataFrame([_row("reels", 1500, 80, 0)])], ignore_index=True)

    result = analyze_dimension(df, "placement", CFG)

    assert result.benchmark_cpa == pytest.approx(705.88, abs=0.01)
    seg = _by_segment(result)
    assert seg["reels"].is_flagged and seg["reels"].flag_reason == "zero_conversions"
    assert seg["reels"].wasted_spend == 1500
    assert seg["audience_network"].wasted_spend == pytest.approx(5176.47, abs=0.01)
    assert result.total_wasted_spend == pytest.approx(6676.47, abs=0.01)


def test_best_benchmark_mode_uses_cheapest_segment_with_enough_conversions():
    cfg = PipelineConfig.from_overrides({**CFG.to_dict(), "benchmark_mode": "best"})

    result = analyze_dimension(_base_df(), "placement", cfg)

    assert result.benchmark_cpa == 500
    assert [s.segment for s in result.flagged] == ["audience_network"]
    assert _by_segment(result)["audience_network"].wasted_spend == pytest.approx(6000.0)


def test_segments_sorted_by_spend_descending_and_rates_computed():
    result = analyze_dimension(_base_df(), "placement", CFG)

    assert [s.segment for s in result.segments] == ["feed", "audience_network", "stories", "tiny"]
    feed = _by_segment(result)["feed"]
    assert feed.ctr == pytest.approx(500 / 10000)
    assert feed.cvr == pytest.approx(20 / 500)
    assert feed.roas == pytest.approx(50000 / 10000)


def test_rows_with_blank_dimension_are_excluded_for_that_dimension_only():
    df = pd.concat(
        [_base_df(), pd.DataFrame([_row("feed", 3000, 100, 5, time_slot="")])],
        ignore_index=True,
    )

    by_time = analyze_dimension(df, "time_slot", CFG)
    by_placement = analyze_dimension(df, "placement", CFG)

    assert by_time.total_spend == pytest.approx(24200)  # blank row dropped
    assert by_placement.total_spend == pytest.approx(27200)  # blank row kept


def test_no_significant_segments_means_no_benchmark_and_no_flags():
    df = pd.DataFrame([_row("a", 100, 3, 0), _row("b", 200, 4, 1)])

    result = analyze_dimension(df, "placement", CFG)

    assert result.benchmark_cpa is None
    assert result.flagged == []
    assert result.total_wasted_spend == 0


def test_all_zero_conversions_gives_no_benchmark_but_flags_zero_conv_segments():
    df = pd.DataFrame([_row("a", 3000, 100, 0), _row("b", 4000, 120, 0)])

    result = analyze_dimension(df, "placement", CFG)

    assert result.benchmark_cpa is None
    assert sorted(s.segment for s in result.flagged) == ["a", "b"]
    assert result.total_wasted_spend == 7000


def test_analyze_all_dimensions_returns_every_dimension():
    results = analyze_all_dimensions(_base_df(), CFG)

    assert set(results) == {"placement", "age_group", "time_slot"}
    assert results["age_group"].segments[0].segment == "25-34"


def test_zero_conversion_segment_does_not_inflate_benchmark():
    df = pd.DataFrame(
        [
            _row("A", 84000, 2000, 40),
            _row("B", 40000, 1500, 50),
            _row("D", 6000, 200, 0),
        ]
    )

    result = analyze_dimension(df, "placement", CFG)

    assert result.benchmark_cpa == pytest.approx(1377.7778, abs=0.01)
    seg = _by_segment(result)
    assert seg["A"].flag_reason == "high_cpa"
    assert seg["A"].wasted_spend == pytest.approx(28888.89, abs=0.01)
    assert seg["D"].flag_reason == "zero_conversions"
    assert seg["D"].wasted_spend == 6000.0
    assert result.total_wasted_spend == pytest.approx(34888.89, abs=0.01)


def test_empty_dimension_totals_are_floats():
    df = pd.DataFrame([_row("feed", 5000, 200, 10, time_slot="")])

    result = analyze_dimension(df, "time_slot", CFG)

    assert result.segments == []
    assert isinstance(result.total_wasted_spend, float)
    assert result.total_wasted_spend == 0.0


def test_single_segment_dimension_is_never_flagged():
    df = pd.DataFrame([_row("feed", 20000, 800, 10)])

    result = analyze_dimension(df, "placement", CFG)

    assert result.benchmark_cpa == 2000.0
    seg = _by_segment(result)
    assert seg["feed"].is_flagged is False
    assert result.total_wasted_spend == 0.0
    assert result.flagged == []
