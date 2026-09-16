from pathlib import Path

from app.pipeline.data_generator import write_sample_csv
from app.pipeline.run import main

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_cli_prints_headline_and_flagged_segment(tmp_path, capsys):
    path = write_sample_csv(
        tmp_path / "s.csv", days=30, seed=42, waste={"placement": {"audience_network": 3.0}}
    )

    exit_code = main([str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Headline waste" in out
    assert "audience_network" in out
    assert "Audience Network spent Rs." in out


def test_cli_reports_validation_errors_and_exits_2(capsys):
    exit_code = main([str(FIXTURES / "bad_numbers.csv")])

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "row 1, spend" in out


def test_cli_accepts_json_overrides(tmp_path, capsys):
    path = write_sample_csv(tmp_path / "s.csv", days=10, seed=1)

    exit_code = main([str(path), "--overrides", '{"waste_multiplier": 0.5}'])

    assert exit_code == 0
    assert "waste_multiplier=0.5" in capsys.readouterr().out
