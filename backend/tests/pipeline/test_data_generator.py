from pathlib import Path

from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.config import REQUIRED_COLUMNS, PipelineConfig
from app.pipeline.data_generator import generate_dataset, write_sample_csv
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import headline_waste


def test_generated_frame_has_required_columns_and_is_deterministic():
    a = generate_dataset(days=5, seed=1)
    b = generate_dataset(days=5, seed=1)

    assert list(a.columns) == list(REQUIRED_COLUMNS)
    assert a.equals(b)
    assert len(a) == 5 * 4 * 5 * 3 * 4  # days × placements × age groups × devices × time slots


def test_golden_injected_placement_waste_is_found_and_nothing_else_is_flagged():
    df = generate_dataset(days=30, seed=42, waste={"placement": {"audience_network": 3.0}})

    results = analyze_all_dimensions(df, PipelineConfig())

    assert [s.segment for s in results["placement"].flagged] == ["audience_network"]
    assert results["age_group"].flagged == []
    assert results["time_slot"].flagged == []
    an = next(s for s in results["placement"].segments if s.segment == "audience_network")
    assert 0 < an.wasted_spend <= an.spend
    assert an.cpa > 2.0 * results["placement"].benchmark_cpa
    assert headline_waste(results) == results["placement"].total_wasted_spend


def test_golden_clean_account_has_no_flags():
    results = analyze_all_dimensions(generate_dataset(days=30, seed=7), PipelineConfig())

    assert all(r.flagged == [] for r in results.values())


def test_golden_two_dimensions_flag_independently():
    df = generate_dataset(
        days=30, seed=3, waste={"placement": {"audience_network": 3.0}, "time_slot": {"night": 2.5}}
    )

    results = analyze_all_dimensions(df, PipelineConfig())

    assert [s.segment for s in results["placement"].flagged] == ["audience_network"]
    assert [s.segment for s in results["time_slot"].flagged] == ["night"]


def test_written_csv_round_trips_through_loader(tmp_path: Path):
    path = write_sample_csv(tmp_path / "sample.csv", days=3, seed=5)

    result = load_csv(path)

    assert result.ok, result.errors
    assert result.row_count == 3 * 4 * 5 * 3 * 4
    assert result.warnings == []


def test_sample_csv_uses_lf_line_endings(tmp_path: Path):
    df = generate_dataset(days=3, seed=5)
    path = write_sample_csv(tmp_path / "sample.csv", days=3, seed=5)

    data = path.read_bytes()

    assert b"\r\n" not in data
    assert data.count(b"\n") == len(df) + 1
