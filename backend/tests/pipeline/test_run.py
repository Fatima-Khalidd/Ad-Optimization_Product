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

    # waste_multiplier must be > 1 (see PipelineConfig.from_overrides validation).
    exit_code = main([str(path), "--overrides", '{"waste_multiplier": 2.0}'])

    assert exit_code == 0
    assert "waste_multiplier=2.0" in capsys.readouterr().out


def test_missing_file_exits_2_with_message(capsys):
    exit_code = main(["does_not_exist.csv"])

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "error: file not found: does_not_exist.csv" in err


def test_invalid_overrides_json_exits_2(tmp_path, capsys):
    path = write_sample_csv(tmp_path / "s.csv", days=10, seed=1)

    exit_code = main([str(path), "--overrides", "{not json"])

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "error: invalid --overrides:" in err


def test_unknown_override_key_exits_2(tmp_path, capsys):
    path = write_sample_csv(tmp_path / "s.csv", days=10, seed=1)

    exit_code = main([str(path), "--overrides", '{"nope": 1}'])

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "error: invalid --overrides:" in err


def test_non_object_overrides_exits_2_with_clear_message(tmp_path, capsys):
    path = write_sample_csv(tmp_path / "s.csv", days=10, seed=1)

    exit_code = main([str(path), "--overrides", "[1,2]"])

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "error: invalid --overrides: must be a JSON object" in err


def test_cli_prints_account_spend_before_headline_waste(tmp_path, capsys):
    path = write_sample_csv(tmp_path / "s.csv", days=10, seed=1)

    exit_code = main([str(path)])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Account spend: Rs." in out
    assert out.index("Account spend:") < out.index("Headline waste")
