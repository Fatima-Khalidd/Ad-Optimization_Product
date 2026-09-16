"""Write the 30-day demo CSV used for hand-checking and Stage 3+ demos."""

from pathlib import Path

from app.pipeline.data_generator import write_sample_csv

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_30d.csv"
    write_sample_csv(out, days=30, seed=42, waste={"placement": {"audience_network": 3.0}})
    print(f"wrote {out}")
