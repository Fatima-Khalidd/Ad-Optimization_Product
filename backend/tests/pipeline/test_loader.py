import io
from datetime import date
from pathlib import Path

import pandas as pd

from app.pipeline.config import PipelineConfig
from app.pipeline.loader import load_csv

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_valid_file_loads_with_normalised_categories_and_types():
    result = load_csv(FIXTURES / "minimal_valid.csv")

    assert result.ok, result.errors
    df = result.df
    assert result.row_count == 3
    assert result.date_range == (date(2026, 8, 1), date(2026, 8, 2))
    assert list(df["placement"]) == ["facebook_feed", "audience_network", "instagram_stories"]
    assert list(df["gender"]) == ["male", "female", "unknown"]
    assert list(df["device"]) == ["mobile", "mobile", "desktop"]
    assert list(df["time_slot"]) == ["morning", "evening", "afternoon"]
    assert df["spend"].dtype.kind == "f"
    assert df["clicks"].dtype.kind == "i"
    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert result.warnings == []


def test_missing_column_is_a_file_level_error():
    result = load_csv(FIXTURES / "missing_column.csv")

    assert not result.ok
    assert result.df is None
    assert [e.row for e in result.errors] == [None]
    assert "time_slot" in result.errors[0].message


def test_bad_numbers_report_row_and_column():
    result = load_csv(FIXTURES / "bad_numbers.csv")

    assert not result.ok
    issues = {(e.row, e.column) for e in result.errors}
    assert (1, "spend") in issues  # "abc"
    assert (2, "spend") in issues  # negative
    assert (3, "clicks") in issues  # clicks > impressions
    assert (4, "date") in issues  # unparseable date


def test_blank_dimensions_are_allowed_and_kept_blank():
    result = load_csv(FIXTURES / "partial_dimensions.csv")

    assert result.ok, result.errors
    df = result.df
    assert list(df["placement"]) == ["facebook_feed", "", "", "facebook_feed"]
    assert list(df["time_slot"]) == ["", "", "morning", "morning"]


def test_conversions_above_clicks_is_a_warning_not_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01,C1,feed,25-34,m,mobile,9,100,1000,10,15,500\n"
    )
    result = load_csv(csv)

    assert result.ok
    assert [(w.row, w.column) for w in result.warnings] == [(1, "conversions")]


def test_duplicate_rows_and_unknown_device_are_warnings():
    row = "2026-08-01,C1,feed,25-34,m,smartwatch,9,100,1000,10,1,500\n"
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        + row
        + row
    )
    result = load_csv(csv)

    assert result.ok
    messages = " | ".join(w.message for w in result.warnings)
    assert "duplicate" in messages
    assert "smartwatch" in messages


def test_empty_file_is_an_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
    )
    result = load_csv(csv)

    assert not result.ok
    assert "no data rows" in result.errors[0].message


def test_too_many_rows_is_an_error():
    header = "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
    row = "2026-08-01,C1,feed,25-34,m,mobile,9,100,1000,10,1,500\n"
    result = load_csv(io.StringIO(header + row * 3), PipelineConfig.from_overrides({"max_rows": 2}))

    assert not result.ok
    assert "max_rows" in result.errors[0].message


def test_time_slot_hour_out_of_range_is_an_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01,C1,feed,25-34,m,mobile,27,100,1000,10,1,500\n"
    )
    result = load_csv(csv)

    assert not result.ok
    assert (result.errors[0].row, result.errors[0].column) == (1, "time_slot")


def test_age_group_keeps_hyphen_and_campaign_id_is_only_trimmed():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01, CAMP-001 ,FB Feed, 25-34 ,m,mobile,9,100,1000,10,1,500\n"
    )
    result = load_csv(csv)

    assert result.ok, result.errors
    df = result.df
    assert df["age_group"].iloc[0] == "25-34"
    assert df["campaign_id"].iloc[0] == "CAMP-001"
    assert df["placement"].iloc[0] == "facebook_feed"


def test_non_integer_in_count_column_is_an_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01,C1,feed,25-34,m,mobile,9,100,1000,20.5,1,500\n"
    )
    result = load_csv(csv)

    assert not result.ok
    assert any(e.column == "clicks" and e.row == 1 for e in result.errors)


def test_infinite_spend_is_an_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01,C1,feed,25-34,m,mobile,9,inf,1000,10,1,500\n"
    )
    result = load_csv(csv)

    assert result.ok is False
    assert any(e.column == "spend" and e.row == 1 for e in result.errors)


def test_negative_infinite_spend_is_an_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01,C1,feed,25-34,m,mobile,9,-inf,1000,10,1,500\n"
    )
    result = load_csv(csv)

    assert result.ok is False
    assert any(e.column == "spend" and e.row == 1 for e in result.errors)


def test_nan_text_spend_is_an_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01,C1,feed,25-34,m,mobile,9,nan,1000,10,1,500\n"
    )
    result = load_csv(csv)

    assert result.ok is False
    assert any(e.column == "spend" and e.row == 1 for e in result.errors)


def test_zero_byte_file_is_an_error():
    result = load_csv(io.StringIO(""))

    assert not result.ok
    assert result.df is None
    assert result.errors[0].row is None
    assert result.errors[0].column is None
    assert "empty" in result.errors[0].message


def test_non_utf8_file_is_an_error(tmp_path):
    path = tmp_path / "latin1.csv"
    header = (
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,"
        "clicks,conversions,revenue\n"
    )
    row = "2026-08-01,café,feed,25-34,m,mobile,9,100,1000,10,1,500\n"
    with open(path, "wb") as f:
        f.write(header.encode("utf-8"))
        f.write(row.encode("latin-1"))

    result = load_csv(path)

    assert not result.ok
    assert result.df is None
    assert result.errors[0].row is None
    assert "utf-8" in result.errors[0].message.lower()


def test_malformed_csv_raises_parser_error_is_handled():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,"
        "clicks,conversions,revenue\n"
        '2026-08-01,"C1,feed,25-34,m,mobile,9,100,1000,10,1,500\n'
        "2026-08-02,C2,feed,25-34,m,mobile,9,100,1000,10,1,500\n"
    )
    result = load_csv(csv)

    assert not result.ok
    assert result.df is None
    assert result.errors[0].row is None
    assert "could not parse csv" in result.errors[0].message.lower()


def test_blank_campaign_id_is_an_error():
    csv = io.StringIO(
        "date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue\n"
        "2026-08-01,,feed,25-34,m,mobile,9,100,1000,10,1,500\n"
    )
    result = load_csv(csv)

    assert not result.ok
    assert any(e.column == "campaign_id" and e.row == 1 for e in result.errors)
