from decimal import Decimal

import pytest

from app.pipeline.config import DIMENSIONS, REQUIRED_COLUMNS, PipelineConfig


def test_defaults_match_design_doc():
    cfg = PipelineConfig()
    assert cfg.waste_multiplier == 1.5
    assert cfg.benchmark_mode == "account_avg"
    assert cfg.min_spend == 5000
    assert cfg.min_clicks == 100
    assert cfg.max_cut_pct == 0.6
    assert cfg.base_fee == Decimal("15000")
    assert cfg.performance_fee_pct == Decimal("20")
    assert cfg.performance_fee_cap is None


def test_dimensions_and_required_columns():
    assert DIMENSIONS == ("placement", "age_group", "time_slot")
    assert REQUIRED_COLUMNS == (
        "date",
        "campaign_id",
        "placement",
        "age_group",
        "gender",
        "device",
        "time_slot",
        "spend",
        "impressions",
        "clicks",
        "conversions",
        "revenue",
    )


def test_from_overrides_replaces_only_named_fields():
    cfg = PipelineConfig.from_overrides({"waste_multiplier": 2.0, "min_spend": 1000})
    assert cfg.waste_multiplier == 2.0
    assert cfg.min_spend == 1000
    assert cfg.min_clicks == 100  # untouched default


def test_from_overrides_rejects_unknown_key():
    with pytest.raises(ValueError, match="unknown config key: typo_key"):
        PipelineConfig.from_overrides({"typo_key": 1})


def test_from_overrides_rejects_bad_benchmark_mode():
    with pytest.raises(ValueError, match="benchmark_mode"):
        PipelineConfig.from_overrides({"benchmark_mode": "median"})


def test_to_dict_is_json_safe_and_roundtrips():
    import json

    cfg = PipelineConfig.from_overrides({"performance_fee_cap": Decimal("50000")})
    snapshot = cfg.to_dict()
    json.dumps(snapshot)  # must not raise
    assert snapshot["performance_fee_cap"] == "50000"
    assert PipelineConfig.from_overrides(snapshot) == cfg


@pytest.mark.parametrize(
    "override",
    [
        {"min_spend": "abc"},
        {"min_clicks": -10},
        {"waste_multiplier": 1.0},
        {"performance_fee_pct": -5},
        {"max_rows": 0},
        {"max_cut_pct": 1.5},
        {"min_clicks": True},
    ],
)
def test_from_overrides_rejects_bad_values(override):
    with pytest.raises(ValueError):
        PipelineConfig.from_overrides(override)


def test_from_overrides_coerces_numeric_strings_and_whole_number_floats():
    cfg = PipelineConfig.from_overrides({"min_spend": "6000", "min_clicks": 150.0})

    assert cfg.min_spend == 6000.0
    assert isinstance(cfg.min_spend, float)
    assert cfg.min_clicks == 150
    assert isinstance(cfg.min_clicks, int)
