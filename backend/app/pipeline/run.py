"""Command-line runner so the owner can hand-check a report: python -m app.pipeline.run file.csv"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.pipeline.analyzer import account_total_spend, analyze_all_dimensions
from app.pipeline.config import PipelineConfig
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import build_recommendations, headline_waste


def _fmt(amount: float | None) -> str:
    return "-" if amount is None else f"{amount:,.0f}"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    parser = argparse.ArgumentParser(description="Run the waste analysis on a CSV.")
    parser.add_argument("csv")
    parser.add_argument("--overrides", default="{}", help="JSON, e.g. '{\"waste_multiplier\": 2}'")
    args = parser.parse_args(argv)

    if not Path(args.csv).is_file():
        print(f"error: file not found: {args.csv}", file=sys.stderr)
        return 2

    try:
        parsed_overrides = json.loads(args.overrides)
    except json.JSONDecodeError as exc:
        print(f"error: invalid --overrides: {exc}", file=sys.stderr)
        return 2
    if not isinstance(parsed_overrides, dict):
        print("error: invalid --overrides: must be a JSON object", file=sys.stderr)
        return 2

    try:
        config = PipelineConfig.from_overrides(parsed_overrides)
    except ValueError as exc:
        print(f"error: invalid --overrides: {exc}", file=sys.stderr)
        return 2

    result = load_csv(args.csv, config)
    for w in result.warnings[:20]:
        print(f"warning: row {w.row}, {w.column}: {w.message}")
    if not result.ok:
        print("VALIDATION FAILED")
        for e in result.errors[:50]:
            where = f"row {e.row}, {e.column}" if e.row is not None else "file"
            print(f"  {where}: {e.message}")
        return 2

    results = analyze_all_dimensions(result.df, config)
    recs = build_recommendations(results, config)

    print(f"Rows: {result.row_count}   Dates: {result.date_range[0]} to {result.date_range[1]}")
    print(f"Config: {', '.join(f'{k}={v}' for k, v in config.to_dict().items())}")
    print(f"Account spend: Rs. {_fmt(account_total_spend(result.df))}")
    print(f"Headline waste: Rs. {_fmt(headline_waste(results))}\n")
    for dim, r in results.items():
        print(
            f"== {dim}  (spend {_fmt(r.total_spend)}, waste {_fmt(r.total_wasted_spend)}, "
            f"benchmark CPA {_fmt(r.benchmark_cpa)})"
        )
        print(f"{'segment':<22}{'spend':>12}{'conv':>7}{'CPA':>9}{'flag':>18}{'waste':>12}")
        for s in r.segments:
            flag = s.flag_reason or ("" if s.is_significant else "(not significant)")
            print(
                f"{s.segment:<22}{_fmt(s.spend):>12}{s.conversions:>7}{_fmt(s.cpa):>9}"
                f"{flag:>18}{_fmt(s.wasted_spend):>12}"
            )
        print()
    print("Recommendations:")
    for rec in recs:
        print(f"  - {rec.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
