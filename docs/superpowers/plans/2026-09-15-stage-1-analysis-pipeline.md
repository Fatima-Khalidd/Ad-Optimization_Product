# Stage 1 — Analysis Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A pure-Python, fully tested pipeline (`config → loader → analyzer → optimizer`) that turns an ad-account CSV into flagged wasteful segments, rupee-accurate waste figures, plain-language recommendations, and a `Decimal` fee breakdown — runnable from the command line on a sample file.

**Architecture:** Everything lives in `backend/app/pipeline/` and imports **no database or web code** — only pandas, numpy and the standard library — so every function is testable with a DataFrame in hand. Every tunable number lives in `PipelineConfig`; nothing is hardcoded in analysis code. Tests are a mix of hand-computed unit tests (exact numbers) and golden tests on synthetic data with injected waste (exact flagged sets).

**Tech Stack:** Python 3.11, pandas 3.0, numpy 2.4, pytest 9, pytest-cov 7. Depends on Stage 0's venv and `pyproject.toml`.

**Spec:** `docs/PLAN.md` §3 "Analysis methodology" (authoritative for every formula below), §1 #1/#2/#3/#6, §6 "Stage 1".

## Global Constraints

- The pipeline package imports nothing from `app.core`, `app.models`, FastAPI or SQLAlchemy (§2: "PURE analysis logic: no DB, no web imports").
- Every threshold is a `PipelineConfig` field with a default; analysis code reads it from the config object only (§3).
- **Headline waste is the largest single-dimension total, never the sum across dimensions** (§1 #1).
- Default benchmark is `account_avg`; `best` is a config option (§1 #2).
- Rows may have blank dimension values; each dimension is analyzed only on rows that have it (§1 #3).
- Fees are computed with `Decimal` and quantized to 2 places, `ROUND_HALF_UP` (§1 #6). pandas floats are fine inside analysis.
- Coverage for `app/pipeline/` must be ≥ 90% (§3 "Test strategy").
- Pricing defaults (`base_fee`, `performance_fee_pct`) are placeholders awaiting the user's decision (`docs/PLAN.md` §7 #4) — keep them in config, never elsewhere.

---

## File Structure

```
backend/
├── requirements.txt                 # + pandas, numpy
├── pyproject.toml                   # + coverage settings
├── app/pipeline/
│   ├── __init__.py
│   ├── config.py                    # PipelineConfig dataclass + from_overrides()
│   ├── loader.py                    # load_csv(): validation → clean DataFrame + report
│   ├── analyzer.py                  # analyze_dimension(), analyze_all_dimensions()
│   ├── optimizer.py                 # build_recommendations(), headline_waste(), calculate_fee()
│   ├── data_generator.py            # generate_dataset() with injected waste
│   └── run.py                       # CLI: python -m app.pipeline.run file.csv
└── tests/
    ├── fixtures/
    │   ├── minimal_valid.csv
    │   ├── missing_column.csv
    │   ├── bad_numbers.csv
    │   └── partial_dimensions.csv
    └── pipeline/
        ├── __init__.py
        ├── test_config.py
        ├── test_loader.py
        ├── test_analyzer.py
        ├── test_optimizer.py
        ├── test_data_generator.py   # golden tests
        └── test_run.py
```

---

### Task 1: `PipelineConfig`

**Files:**
- Modify: `backend/requirements.txt` (add pandas, numpy)
- Modify: `backend/pyproject.toml` (coverage config)
- Create: `backend/app/pipeline/__init__.py`
- Create: `backend/app/pipeline/config.py`
- Create: `backend/tests/pipeline/__init__.py`
- Test: `backend/tests/pipeline/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  ```python
  DIMENSIONS: tuple[str, ...] = ("placement", "age_group", "time_slot")
  REQUIRED_COLUMNS: tuple[str, ...]
  @dataclass(frozen=True) class PipelineConfig: ...   # fields listed in Step 3
  PipelineConfig.from_overrides(overrides: dict) -> PipelineConfig   # raises ValueError on unknown key
  PipelineConfig.to_dict() -> dict                                   # JSON-safe snapshot
  ```

- [ ] **Step 1: Add pandas/numpy and coverage settings**

Append to `backend/requirements.txt`:
```text
pandas==3.0.5
numpy==2.4.6
```
Run: `cd backend && .venv/Scripts/python -m pip install -r requirements-dev.txt`
Expected: `Successfully installed numpy-2.4.6 pandas-3.0.5 ...`

Append to `backend/pyproject.toml`:
```toml
[tool.coverage.run]
source = ["app/pipeline"]

[tool.coverage.report]
show_missing = true
fail_under = 90
```

- [ ] **Step 2: Write the failing test**

`backend/tests/pipeline/__init__.py`: empty. `backend/app/pipeline/__init__.py`: empty.

`backend/tests/pipeline/test_config.py`:
```python
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
        "date", "campaign_id", "placement", "age_group", "gender", "device",
        "time_slot", "spend", "impressions", "clicks", "conversions", "revenue",
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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.config'`

- [ ] **Step 4: Write the implementation**

`backend/app/pipeline/config.py`:
```python
"""Every tunable number in the analysis lives here. Nothing else hardcodes a threshold."""

from dataclasses import asdict, dataclass, fields
from decimal import Decimal
from typing import Any, Literal

DIMENSIONS: tuple[str, ...] = ("placement", "age_group", "time_slot")

REQUIRED_COLUMNS: tuple[str, ...] = (
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

# Columns that may be blank on a row (Meta exports can't combine every breakdown).
OPTIONAL_DIMENSIONS: tuple[str, ...] = ("placement", "age_group", "gender", "device", "time_slot")

BenchmarkMode = Literal["account_avg", "best"]

# Inclusive hour ranges. A numeric time_slot 0-23 is mapped to one of these names.
TIME_SLOT_BUCKETS: dict[str, tuple[int, int]] = {
    "night": (0, 5),
    "morning": (6, 11),
    "afternoon": (12, 17),
    "evening": (18, 23),
}

# Normalised value -> canonical value, per column.
CATEGORY_ALIASES: dict[str, dict[str, str]] = {
    "placement": {
        "feed": "facebook_feed",
        "fb_feed": "facebook_feed",
        "ig_feed": "instagram_feed",
        "ig_stories": "instagram_stories",
        "stories": "instagram_stories",
        "an": "audience_network",
    },
    "device": {"phone": "mobile", "smartphone": "mobile", "pc": "desktop"},
    "gender": {"m": "male", "f": "female", "u": "unknown", "": ""},
}

# Values outside these sets produce a warning (not an error).
KNOWN_VALUES: dict[str, set[str]] = {
    "device": {"mobile", "desktop", "tablet"},
    "gender": {"male", "female", "unknown"},
}

_DECIMAL_FIELDS = {"base_fee", "performance_fee_pct", "performance_fee_cap"}


@dataclass(frozen=True)
class PipelineConfig:
    # --- significance: segments below these are shown but never flagged ---
    min_spend: float = 5000.0
    min_clicks: int = 100
    # --- flagging ---
    benchmark_mode: BenchmarkMode = "account_avg"
    waste_multiplier: float = 1.5
    min_spend_zero_conv: float = 2000.0
    min_conversions_for_best: int = 10
    # --- recommendations ---
    max_cut_pct: float = 0.6
    # --- upload limits ---
    max_upload_mb: int = 20
    max_rows: int = 500_000
    # --- pricing (PLACEHOLDERS until the owner decides; see docs/PLAN.md section 7 #4) ---
    base_fee: Decimal = Decimal("15000")
    performance_fee_pct: Decimal = Decimal("20")
    performance_fee_cap: Decimal | None = None

    @classmethod
    def from_overrides(cls, overrides: dict[str, Any]) -> "PipelineConfig":
        known = {f.name for f in fields(cls)}
        values: dict[str, Any] = {}
        for key, value in overrides.items():
            if key not in known:
                raise ValueError(f"unknown config key: {key}")
            if key in _DECIMAL_FIELDS and value is not None:
                value = Decimal(str(value))
            values[key] = value
        cfg = cls(**values)
        if cfg.benchmark_mode not in ("account_avg", "best"):
            raise ValueError(f"benchmark_mode must be 'account_avg' or 'best', got {cfg.benchmark_mode!r}")
        return cfg

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in _DECIMAL_FIELDS:
            if data[key] is not None:
                data[key] = str(data[key])
        return data
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_config.py -v`
Expected: `6 passed`

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/requirements.txt backend/pyproject.toml backend/app/pipeline backend/tests/pipeline
git commit -m "feat(pipeline): PipelineConfig with every tunable threshold"
```

---

### Task 2: `loader.py` — CSV validation and normalisation

**Files:**
- Create: `backend/app/pipeline/loader.py`
- Create: `backend/tests/fixtures/minimal_valid.csv`, `missing_column.csv`, `bad_numbers.csv`, `partial_dimensions.csv`
- Test: `backend/tests/pipeline/test_loader.py`

**Interfaces:**
- Consumes: `REQUIRED_COLUMNS`, `OPTIONAL_DIMENSIONS`, `TIME_SLOT_BUCKETS`, `CATEGORY_ALIASES`, `KNOWN_VALUES`, `PipelineConfig`.
- Produces:
  ```python
  @dataclass class RowIssue: row: int | None; column: str | None; message: str   # row is 1-based data row (header = row 0)
  @dataclass class LoadResult:
      df: pd.DataFrame | None        # None when errors is non-empty
      errors: list[RowIssue]
      warnings: list[RowIssue]
      row_count: int
      date_range: tuple[date, date] | None
      @property ok -> bool
  def load_csv(source: str | Path | IO[str] | IO[bytes], config: PipelineConfig | None = None) -> LoadResult
  ```
  Clean `df` guarantees: all `REQUIRED_COLUMNS` present; `date` is `datetime64`; `spend`, `revenue` float; `impressions`, `clicks`, `conversions` int; category columns are lowercase snake_case strings, `""` where blank; `time_slot` is one of `TIME_SLOT_BUCKETS` keys or `""`.

- [ ] **Step 1: Create the fixtures**

`backend/tests/fixtures/minimal_valid.csv`:
```csv
date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue
2026-08-01,C1,FB Feed,25-34,M,Phone,9,1200.50,10000,250,5,12500
2026-08-01,C1,Audience Network,25-34,F,mobile,evening,800,9000,180,0,0
2026-08-02,C1,ig_stories,18-24,U,desktop,14,300,2000,40,1,2500
```

`backend/tests/fixtures/missing_column.csv`:
```csv
date,campaign_id,placement,age_group,gender,device,spend,impressions,clicks,conversions,revenue
2026-08-01,C1,feed,25-34,m,mobile,100,1000,20,1,500
```

`backend/tests/fixtures/bad_numbers.csv`:
```csv
date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue
2026-08-01,C1,feed,25-34,m,mobile,9,abc,1000,20,1,500
2026-08-02,C1,feed,25-34,m,mobile,9,-50,1000,20,1,500
2026-08-03,C1,feed,25-34,m,mobile,9,100,1000,2000,1,500
not-a-date,C1,feed,25-34,m,mobile,9,100,1000,20,1,500
```

`backend/tests/fixtures/partial_dimensions.csv`:
```csv
date,campaign_id,placement,age_group,gender,device,time_slot,spend,impressions,clicks,conversions,revenue
2026-08-01,C1,feed,,,,,1000,5000,100,4,10000
2026-08-01,C1,,25-34,,,,1000,5000,100,4,10000
2026-08-01,C1,,,,,morning,1000,5000,100,4,10000
2026-08-01,C1,feed,25-34,m,mobile,9,500,2500,50,3,7500
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/pipeline/test_loader.py`:
```python
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
    assert (1, "spend") in issues          # "abc"
    assert (2, "spend") in issues          # negative
    assert (3, "clicks") in issues         # clicks > impressions
    assert (4, "date") in issues           # unparseable date


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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.loader'`

- [ ] **Step 4: Write the implementation**

`backend/app/pipeline/loader.py`:
```python
"""Validate an uploaded ad-account CSV and return a clean DataFrame plus a row-level report."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import IO

import pandas as pd

from app.pipeline.config import (
    CATEGORY_ALIASES,
    KNOWN_VALUES,
    REQUIRED_COLUMNS,
    TIME_SLOT_BUCKETS,
    PipelineConfig,
)

NUMERIC_FLOAT = ("spend", "revenue")
NUMERIC_INT = ("impressions", "clicks", "conversions")
CATEGORY_COLUMNS = ("campaign_id", "placement", "age_group", "gender", "device", "time_slot")


@dataclass
class RowIssue:
    row: int | None  # 1-based data row; None = whole-file issue
    column: str | None
    message: str


@dataclass
class LoadResult:
    df: pd.DataFrame | None
    errors: list[RowIssue] = field(default_factory=list)
    warnings: list[RowIssue] = field(default_factory=list)
    row_count: int = 0
    date_range: tuple[date, date] | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def _normalise_category(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[\s\-]+", "_", value)
    return value


def _bucket_time_slot(value: str) -> str | None:
    """Return a bucket name, '' for blank, or None if invalid."""
    if value == "":
        return ""
    if value in TIME_SLOT_BUCKETS:
        return value
    if value.isdigit():
        hour = int(value)
        for name, (lo, hi) in TIME_SLOT_BUCKETS.items():
            if lo <= hour <= hi:
                return name
    return None


def load_csv(
    source: str | Path | IO[str] | IO[bytes], config: PipelineConfig | None = None
) -> LoadResult:
    config = config or PipelineConfig()
    errors: list[RowIssue] = []
    warnings: list[RowIssue] = []

    raw = pd.read_csv(source, dtype=str, keep_default_na=False)
    raw.columns = [str(c).strip().lower() for c in raw.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        errors.append(RowIssue(None, None, f"missing required columns: {', '.join(missing)}"))
        return LoadResult(None, errors, warnings)

    if len(raw) == 0:
        errors.append(RowIssue(None, None, "file has no data rows"))
        return LoadResult(None, errors, warnings)

    if len(raw) > config.max_rows:
        errors.append(
            RowIssue(None, None, f"file has {len(raw)} rows; max_rows is {config.max_rows}")
        )
        return LoadResult(None, errors, warnings)

    df = raw[list(REQUIRED_COLUMNS)].copy()
    row_numbers = pd.RangeIndex(1, len(df) + 1)

    # --- dates ---
    parsed_dates = pd.to_datetime(df["date"].str.strip(), errors="coerce", format="mixed")
    for r in row_numbers[parsed_dates.isna().to_numpy()]:
        errors.append(RowIssue(int(r), "date", f"unparseable date {df.at[r - 1, 'date']!r}"))
    df["date"] = parsed_dates

    # --- numbers ---
    for col in NUMERIC_FLOAT + NUMERIC_INT:
        stripped = df[col].str.strip().str.replace(",", "", regex=False)
        numeric = pd.to_numeric(stripped, errors="coerce")
        for r in row_numbers[numeric.isna().to_numpy()]:
            errors.append(RowIssue(int(r), col, f"not a number: {df.at[r - 1, col]!r}"))
        for r in row_numbers[(numeric < 0).fillna(False).to_numpy()]:
            errors.append(RowIssue(int(r), col, f"negative value {numeric.iloc[r - 1]}"))
        df[col] = numeric

    for col in NUMERIC_INT:
        non_integer = (df[col] % 1 != 0) & df[col].notna()
        for r in row_numbers[non_integer.to_numpy()]:
            errors.append(RowIssue(int(r), col, f"must be a whole number, got {df.at[r - 1, col]}"))

    # NaN compares False, so rows whose numbers already failed are simply skipped here.
    bad_clicks = df["clicks"] > df["impressions"]
    for r in row_numbers[bad_clicks.to_numpy()]:
        errors.append(RowIssue(int(r), "clicks", "clicks exceed impressions"))
    view_through = df["conversions"] > df["clicks"]
    for r in row_numbers[view_through.to_numpy()]:
        warnings.append(RowIssue(int(r), "conversions", "conversions exceed clicks (view-through?)"))

    # --- categories ---
    for col in CATEGORY_COLUMNS:
        values = df[col].map(_normalise_category)
        aliases = CATEGORY_ALIASES.get(col, {})
        values = values.map(lambda v, a=aliases: a.get(v, v))
        if col == "campaign_id":
            for r in row_numbers[(values == "").to_numpy()]:
                errors.append(RowIssue(int(r), col, "campaign_id is blank"))
        df[col] = values

    bucketed = df["time_slot"].map(_bucket_time_slot)
    for r in row_numbers[bucketed.isna().to_numpy()]:
        errors.append(
            RowIssue(int(r), "time_slot", "time_slot must be an hour 0-23 or a bucket name")
        )
    df["time_slot"] = bucketed.fillna("")

    for col, known in KNOWN_VALUES.items():
        unknown = df[col][(df[col] != "") & ~df[col].isin(known)]
        for r, value in zip(row_numbers[unknown.index.to_numpy()], unknown, strict=True):
            warnings.append(RowIssue(int(r), col, f"unknown {col} value {value!r}"))

    duplicated = df.duplicated(keep="first")
    for r in row_numbers[duplicated.to_numpy()]:
        warnings.append(RowIssue(int(r), None, "duplicate row"))

    if errors:
        return LoadResult(None, errors, warnings)

    for col in NUMERIC_INT:
        df[col] = df[col].astype("int64")
    for col in NUMERIC_FLOAT:
        df[col] = df[col].astype("float64")

    first, last = df["date"].min().date(), df["date"].max().date()
    return LoadResult(df.reset_index(drop=True), errors, warnings, len(df), (first, last))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_loader.py -v`
Expected: `9 passed`. If `test_valid_file_loads...` fails on `gender` because `"u"` maps via alias to `"unknown"` — that's intended; if it fails on `time_slot` for `"9"`, check `_bucket_time_slot` receives the string `"9"` (not int).

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/pipeline/loader.py backend/tests/fixtures backend/tests/pipeline/test_loader.py
git commit -m "feat(pipeline): CSV loader with row-level validation and normalisation"
```

---

### Task 3: `analyzer.py` — per-dimension metrics, benchmark, flags, waste

**Files:**
- Create: `backend/app/pipeline/analyzer.py`
- Test: `backend/tests/pipeline/test_analyzer.py`

**Interfaces:**
- Consumes: `PipelineConfig`, `DIMENSIONS`; a clean `df` from `load_csv`.
- Produces:
  ```python
  @dataclass class SegmentMetrics:
      segment: str; spend: float; impressions: int; clicks: int; conversions: int; revenue: float
      cpa: float | None; ctr: float; cvr: float; roas: float | None
      is_significant: bool; is_flagged: bool; wasted_spend: float; flag_reason: str | None  # "high_cpa" | "zero_conversions" | None
  @dataclass class DimensionResult:
      dimension: str; benchmark_cpa: float | None; total_spend: float; total_wasted_spend: float
      segments: list[SegmentMetrics]           # sorted by spend desc
      @property flagged -> list[SegmentMetrics]
  def analyze_dimension(df: pd.DataFrame, dimension: str, config: PipelineConfig) -> DimensionResult
  def analyze_all_dimensions(df: pd.DataFrame, config: PipelineConfig) -> dict[str, DimensionResult]
  ```

**Hand-computed expectations used in the tests** (config: `min_spend=1000, min_clicks=10, waste_multiplier=1.5, min_spend_zero_conv=500, min_conversions_for_best=5`):

| placement | spend | clicks | conv | CPA |
|---|---|---|---|---|
| feed | 10000 | 500 | 20 | 500 |
| stories | 6000 | 300 | 10 | 600 |
| audience_network | 8000 | 400 | 4 | 2000 |
| tiny | 200 | 5 | 0 | — (not significant) |

- `account_avg` benchmark = 24000 / 34 = **705.88**; threshold 1058.82 → only audience_network flagged; waste = 8000 − 4×705.88 = **5176.47**.
- With an extra `reels` row (spend 1500, clicks 80, conv 0): benchmark = 25500/34 = **750**; reels flagged `zero_conversions` with waste **1500**; AN waste = 8000 − 4×750 = **5000**; dimension total **6500**.
- `best` mode (no reels): best among ≥5 conversions = feed (500); threshold 750 → AN flagged; waste = 8000 − 4×500 = **6000**.

- [ ] **Step 1: Write the failing tests**

`backend/tests/pipeline/test_analyzer.py`:
```python
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

    assert result.benchmark_cpa == pytest.approx(750.0)
    seg = _by_segment(result)
    assert seg["reels"].is_flagged and seg["reels"].flag_reason == "zero_conversions"
    assert seg["reels"].wasted_spend == 1500
    assert seg["audience_network"].wasted_spend == pytest.approx(5000.0)
    assert result.total_wasted_spend == pytest.approx(6500.0)


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

    assert by_time.total_spend == pytest.approx(24200)      # blank row dropped
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.analyzer'`

- [ ] **Step 3: Write the implementation**

`backend/app/pipeline/analyzer.py`:
```python
"""Group spend by dimension, benchmark cost-per-conversion, flag wasteful segments."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.pipeline.config import DIMENSIONS, PipelineConfig

METRIC_COLUMNS = ["spend", "impressions", "clicks", "conversions", "revenue"]


@dataclass
class SegmentMetrics:
    segment: str
    spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float
    cpa: float | None
    ctr: float
    cvr: float
    roas: float | None
    is_significant: bool
    is_flagged: bool
    wasted_spend: float
    flag_reason: str | None


@dataclass
class DimensionResult:
    dimension: str
    benchmark_cpa: float | None
    total_spend: float
    total_wasted_spend: float
    segments: list[SegmentMetrics]

    @property
    def flagged(self) -> list[SegmentMetrics]:
        return [s for s in self.segments if s.is_flagged]


def _benchmark(grouped: pd.DataFrame, config: PipelineConfig) -> float | None:
    """Benchmark CPA across significant segments, or None when there is nothing to compare."""
    sig = grouped[grouped["is_significant"]]
    if config.benchmark_mode == "best":
        candidates = sig[sig["conversions"] >= config.min_conversions_for_best]
        if candidates.empty:
            return None
        return float((candidates["spend"] / candidates["conversions"]).min())
    total_conv = sig["conversions"].sum()
    if total_conv == 0:
        return None
    return float(sig["spend"].sum() / total_conv)


def analyze_dimension(df: pd.DataFrame, dimension: str, config: PipelineConfig) -> DimensionResult:
    rows = df[df[dimension].astype(str) != ""]
    grouped = (
        rows.groupby(dimension, sort=False)[METRIC_COLUMNS]
        .sum()
        .sort_values("spend", ascending=False)
    )
    grouped["is_significant"] = (grouped["spend"] >= config.min_spend) & (
        grouped["clicks"] >= config.min_clicks
    )
    benchmark = _benchmark(grouped, config)

    segments: list[SegmentMetrics] = []
    for name, g in grouped.iterrows():
        conversions = int(g["conversions"])
        clicks = int(g["clicks"])
        impressions = int(g["impressions"])
        spend = float(g["spend"])
        cpa = spend / conversions if conversions else None
        significant = bool(g["is_significant"])

        flag_reason: str | None = None
        wasted = 0.0
        if significant:
            if conversions == 0 and spend >= config.min_spend_zero_conv:
                flag_reason = "zero_conversions"
                wasted = spend
            elif (
                benchmark is not None
                and cpa is not None
                and cpa > config.waste_multiplier * benchmark
            ):
                flag_reason = "high_cpa"
                wasted = max(0.0, spend - conversions * benchmark)

        segments.append(
            SegmentMetrics(
                segment=str(name),
                spend=spend,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                revenue=float(g["revenue"]),
                cpa=cpa,
                ctr=clicks / impressions if impressions else 0.0,
                cvr=conversions / clicks if clicks else 0.0,
                roas=float(g["revenue"]) / spend if spend else None,
                is_significant=significant,
                is_flagged=flag_reason is not None,
                wasted_spend=wasted,
                flag_reason=flag_reason,
            )
        )

    return DimensionResult(
        dimension=dimension,
        benchmark_cpa=benchmark,
        total_spend=float(grouped["spend"].sum()),
        total_wasted_spend=sum(s.wasted_spend for s in segments),
        segments=segments,
    )


def analyze_all_dimensions(df: pd.DataFrame, config: PipelineConfig) -> dict[str, DimensionResult]:
    return {dim: analyze_dimension(df, dim, config) for dim in DIMENSIONS}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_analyzer.py -v`
Expected: `9 passed`

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/pipeline/analyzer.py backend/tests/pipeline/test_analyzer.py
git commit -m "feat(pipeline): per-dimension analyzer with benchmark, flags and waste"
```

---

### Task 4: `optimizer.py` — recommendations, headline waste, fee

**Files:**
- Create: `backend/app/pipeline/optimizer.py`
- Test: `backend/tests/pipeline/test_optimizer.py`

**Interfaces:**
- Consumes: `DimensionResult`, `SegmentMetrics` from Task 3; `PipelineConfig`.
- Produces:
  ```python
  @dataclass class Recommendation: dimension: str; segment_name: str; current_spend: float; recommended_cut: float; reason: str
  @dataclass class FeeBreakdown: base_fee: Decimal; performance_fee: Decimal; total: Decimal; recovered_waste: Decimal; performance_fee_pct: Decimal; cap_applied: bool
  def build_recommendations(results: dict[str, DimensionResult], config: PipelineConfig) -> list[Recommendation]   # sorted by recommended_cut desc
  def headline_waste(results: dict[str, DimensionResult]) -> float                                               # max over dimensions, 0.0 if none
  def calculate_fee(base_fee: Decimal, performance_fee_pct: Decimal, confirmed_recovered_waste: Decimal, cap: Decimal | None = None) -> FeeBreakdown
  ```

- [ ] **Step 1: Write the failing tests**

`backend/tests/pipeline/test_optimizer.py`:
```python
from decimal import Decimal

import pytest

from app.pipeline.analyzer import DimensionResult, SegmentMetrics
from app.pipeline.config import PipelineConfig
from app.pipeline.optimizer import build_recommendations, calculate_fee, headline_waste


def _seg(name, spend, conv, wasted, reason):
    return SegmentMetrics(
        segment=name, spend=spend, impressions=1000, clicks=100, conversions=conv, revenue=0.0,
        cpa=(spend / conv if conv else None), ctr=0.1, cvr=0.0, roas=None,
        is_significant=True, is_flagged=reason is not None, wasted_spend=wasted, flag_reason=reason,
    )


def _results():
    placement = DimensionResult(
        dimension="placement", benchmark_cpa=800.0, total_spend=100000.0, total_wasted_spend=53000.0,
        segments=[
            _seg("audience_network", 84000.0, 40, 52000.0, "high_cpa"),   # cpa 2100
            _seg("reels", 1000.0, 0, 1000.0, "zero_conversions"),
            _seg("feed", 15000.0, 30, 0.0, None),
        ],
    )
    age = DimensionResult(
        dimension="age_group", benchmark_cpa=800.0, total_spend=100000.0, total_wasted_spend=12000.0,
        segments=[_seg("55-64", 20000.0, 5, 12000.0, "high_cpa")],
    )
    time_slot = DimensionResult(
        dimension="time_slot", benchmark_cpa=None, total_spend=0.0, total_wasted_spend=0.0, segments=[]
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
    rec = [r for r in build_recommendations(_results(), PipelineConfig()) if r.segment_name == "reels"][0]

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
    [(Decimal("-1"), Decimal("20"), Decimal("0")), (Decimal("1"), Decimal("120"), Decimal("0")),
     (Decimal("1"), Decimal("20"), Decimal("-5"))],
)
def test_fee_rejects_negative_or_out_of_range_inputs(base, pct, waste):
    with pytest.raises(ValueError):
        calculate_fee(base, pct, waste)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_optimizer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.optimizer'`

- [ ] **Step 3: Write the implementation**

`backend/app/pipeline/optimizer.py`:
```python
"""Turn flagged segments into capped budget cuts, and compute the hybrid fee with Decimal."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.pipeline.analyzer import DimensionResult, SegmentMetrics
from app.pipeline.config import PipelineConfig

TWO_PLACES = Decimal("0.01")


@dataclass
class Recommendation:
    dimension: str
    segment_name: str
    current_spend: float
    recommended_cut: float
    reason: str


@dataclass
class FeeBreakdown:
    base_fee: Decimal
    performance_fee: Decimal
    total: Decimal
    recovered_waste: Decimal
    performance_fee_pct: Decimal
    cap_applied: bool


def _rs(amount: float) -> str:
    return f"Rs. {amount:,.0f}"


def _label(segment: str) -> str:
    return segment.replace("_", " ").title()


def _reason(dimension: str, seg: SegmentMetrics, benchmark: float | None, cut: float) -> str:
    pct = round(cut / seg.spend * 100) if seg.spend else 0
    tail = f"Cut {_rs(cut)} ({pct}%)."
    if seg.flag_reason == "zero_conversions" or seg.cpa is None or benchmark is None:
        return f"{_label(seg.segment)} spent {_rs(seg.spend)} with no conversions at all. {tail}"
    ratio = seg.cpa / benchmark
    return (
        f"{_label(seg.segment)} spent {_rs(seg.spend)} at {_rs(seg.cpa)} per conversion — "
        f"{ratio:.1f}× your {dimension.replace('_', ' ')} average of {_rs(benchmark)}. {tail}"
    )


def build_recommendations(
    results: dict[str, DimensionResult], config: PipelineConfig
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for dimension, result in results.items():
        for seg in result.flagged:
            cut = min(seg.wasted_spend, config.max_cut_pct * seg.spend)
            recs.append(
                Recommendation(
                    dimension=dimension,
                    segment_name=seg.segment,
                    current_spend=seg.spend,
                    recommended_cut=cut,
                    reason=_reason(dimension, seg, result.benchmark_cpa, cut),
                )
            )
    recs.sort(key=lambda r: r.recommended_cut, reverse=True)
    return recs


def headline_waste(results: dict[str, DimensionResult]) -> float:
    """Largest single-dimension waste. Never a sum: the same rupee appears in every dimension."""
    return max((r.total_wasted_spend for r in results.values()), default=0.0)


def calculate_fee(
    base_fee: Decimal,
    performance_fee_pct: Decimal,
    confirmed_recovered_waste: Decimal,
    cap: Decimal | None = None,
) -> FeeBreakdown:
    if base_fee < 0 or confirmed_recovered_waste < 0:
        raise ValueError("base_fee and confirmed_recovered_waste must be >= 0")
    if not (Decimal("0") <= performance_fee_pct <= Decimal("100")):
        raise ValueError("performance_fee_pct must be between 0 and 100")

    performance_fee = (confirmed_recovered_waste * performance_fee_pct / Decimal("100")).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )
    cap_applied = cap is not None and performance_fee > cap
    if cap_applied:
        performance_fee = cap.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    base = base_fee.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return FeeBreakdown(
        base_fee=base,
        performance_fee=performance_fee,
        total=base + performance_fee,
        recovered_waste=confirmed_recovered_waste.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        performance_fee_pct=performance_fee_pct,
        cap_applied=cap_applied,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_optimizer.py -v`
Expected: `11 passed`

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/pipeline/optimizer.py backend/tests/pipeline/test_optimizer.py
git commit -m "feat(pipeline): recommendations, headline waste and Decimal fee calculation"
```

---

### Task 5: `data_generator.py` and golden tests

**Files:**
- Create: `backend/app/pipeline/data_generator.py`
- Test: `backend/tests/pipeline/test_data_generator.py`

**Interfaces:**
- Consumes: `analyze_all_dimensions`, `headline_waste`, `PipelineConfig`, `load_csv`.
- Produces:
  ```python
  def generate_dataset(days: int = 30, seed: int = 42, waste: dict[str, dict[str, float]] | None = None) -> pd.DataFrame
  # waste = {"placement": {"audience_network": 3.0}} → that segment's CPA is ~3× the others
  def write_sample_csv(path: Path, **kwargs) -> Path
  ```
  Generated frame has exactly `REQUIRED_COLUMNS`, one row per (day, placement, age_group, device, time_slot); `time_slot` values are bucket names; revenue = conversions × 2500.

- [ ] **Step 1: Write the failing golden tests**

`backend/tests/pipeline/test_data_generator.py`:
```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_data_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.data_generator'`

- [ ] **Step 3: Write the implementation**

`backend/app/pipeline/data_generator.py`:
```python
"""Synthetic ad-account data with known, injected waste — for tests and demos."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.pipeline.config import REQUIRED_COLUMNS

PLACEMENTS = ("facebook_feed", "instagram_feed", "instagram_stories", "audience_network")
AGE_GROUPS = ("18-24", "25-34", "35-44", "45-54", "55-64")
DEVICES = ("mobile", "desktop", "tablet")
TIME_SLOTS = ("night", "morning", "afternoon", "evening")
GENDERS = ("male", "female")

BASE_CTR = 0.02
BASE_CVR = 0.05
BASE_CPC = 15.0
REVENUE_PER_CONVERSION = 2500.0


def generate_dataset(
    days: int = 30,
    seed: int = 42,
    waste: dict[str, dict[str, float]] | None = None,
) -> pd.DataFrame:
    """One row per (day, placement, age_group, device, time_slot).

    `waste` multiplies the CPA of named segments, e.g. {"placement": {"audience_network": 3.0}}
    makes that placement convert a third as often, so its CPA is ~3x the account average.
    """
    rng = np.random.default_rng(seed)
    waste = waste or {}
    start = date(2026, 8, 1)
    rows = []
    for d in range(days):
        day = start + timedelta(days=d)
        for placement in PLACEMENTS:
            for age in AGE_GROUPS:
                for device in DEVICES:
                    for slot in TIME_SLOTS:
                        multiplier = 1.0
                        multiplier *= waste.get("placement", {}).get(placement, 1.0)
                        multiplier *= waste.get("age_group", {}).get(age, 1.0)
                        multiplier *= waste.get("time_slot", {}).get(slot, 1.0)

                        impressions = int(rng.integers(300, 900))
                        clicks = int(rng.binomial(impressions, BASE_CTR))
                        conversions = int(rng.binomial(clicks, BASE_CVR / multiplier)) if clicks else 0
                        spend = round(clicks * BASE_CPC * float(rng.uniform(0.9, 1.1)), 2)
                        rows.append(
                            {
                                "date": day.isoformat(),
                                "campaign_id": "CAMP-1",
                                "placement": placement,
                                "age_group": age,
                                "gender": GENDERS[int(rng.integers(0, 2))],
                                "device": device,
                                "time_slot": slot,
                                "spend": spend,
                                "impressions": impressions,
                                "clicks": clicks,
                                "conversions": conversions,
                                "revenue": conversions * REVENUE_PER_CONVERSION,
                            }
                        )
    return pd.DataFrame(rows, columns=list(REQUIRED_COLUMNS))


def write_sample_csv(path: Path, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    generate_dataset(**kwargs).to_csv(path, index=False)
    return path
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_data_generator.py -v`
Expected: `5 passed`. If `test_golden_clean_account_has_no_flags` fails because random noise pushed one segment over 1.5× the average, the injected-waste design is wrong, not the seed: check that the loop applies `multiplier` only to `BASE_CVR` and that impressions are ≥ 300 (noise shrinks with volume). Do not "fix" it by changing the seed.

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/pipeline/data_generator.py backend/tests/pipeline/test_data_generator.py
git commit -m "feat(pipeline): synthetic data generator with injected waste and golden tests"
```

---

### Task 6: CLI runner and the hand-check sample

**Files:**
- Create: `backend/app/pipeline/run.py`
- Create: `backend/scripts/generate_sample_data.py`
- Test: `backend/tests/pipeline/test_run.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `python -m app.pipeline.run <file.csv> [--overrides '{"waste_multiplier": 2}']` printing a text report; `run.main(argv: list[str]) -> int` (0 ok, 2 validation failure). `python scripts/generate_sample_data.py` writes `backend/tests/fixtures/sample_30d.csv`.

- [ ] **Step 1: Write the failing test**

`backend/tests/pipeline/test_run.py`:
```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.run'`

- [ ] **Step 3: Write the implementation**

`backend/app/pipeline/run.py`:
```python
"""Command-line runner so the owner can hand-check a report: python -m app.pipeline.run file.csv"""

from __future__ import annotations

import argparse
import json
import sys

from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.config import PipelineConfig
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import build_recommendations, headline_waste


def _fmt(amount: float | None) -> str:
    return "-" if amount is None else f"{amount:,.0f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the waste analysis on a CSV.")
    parser.add_argument("csv")
    parser.add_argument("--overrides", default="{}", help='JSON, e.g. \'{"waste_multiplier": 2}\'')
    args = parser.parse_args(argv)

    config = PipelineConfig.from_overrides(json.loads(args.overrides))
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
    print(f"Headline waste: Rs. {_fmt(headline_waste(results))}\n")
    for dim, r in results.items():
        print(f"== {dim}  (spend {_fmt(r.total_spend)}, waste {_fmt(r.total_wasted_spend)}, "
              f"benchmark CPA {_fmt(r.benchmark_cpa)})")
        print(f"{'segment':<22}{'spend':>12}{'conv':>7}{'CPA':>9}{'flag':>18}{'waste':>12}")
        for s in r.segments:
            flag = s.flag_reason or ("" if s.is_significant else "(not significant)")
            print(f"{s.segment:<22}{_fmt(s.spend):>12}{s.conversions:>7}{_fmt(s.cpa):>9}"
                  f"{flag:>18}{_fmt(s.wasted_spend):>12}")
        print()
    print("Recommendations:")
    for rec in recs:
        print(f"  - {rec.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`backend/scripts/generate_sample_data.py`:
```python
"""Write the 30-day demo CSV used for hand-checking and Stage 3+ demos."""

from pathlib import Path

from app.pipeline.data_generator import write_sample_csv

if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_30d.csv"
    write_sample_csv(out, days=30, seed=42, waste={"placement": {"audience_network": 3.0}})
    print(f"wrote {out}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/pipeline/test_run.py -v`
Expected: `3 passed`

- [ ] **Step 5: Generate the sample and hand-check it (user checkpoint)**

Run:
```bash
cd backend && .venv/Scripts/python scripts/generate_sample_data.py && .venv/Scripts/python -m app.pipeline.run tests/fixtures/sample_30d.csv
```
Expected: a report where `audience_network` is the only flagged placement. Hand-check one number: open `sample_30d.csv` in Excel, filter `placement = audience_network`, sum `spend` and `conversions`; `spend − conversions × (benchmark CPA printed)` must equal the printed waste for that row (±1 rupee from rounding).

- [ ] **Step 6: Commit**

```bash
git add backend/app/pipeline/run.py backend/scripts/generate_sample_data.py backend/tests/fixtures/sample_30d.csv backend/tests/pipeline/test_run.py
git commit -m "feat(pipeline): CLI runner and 30-day sample dataset"
```

---

### Task 7: Coverage gate and README

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:** none new.

- [ ] **Step 1: Run coverage locally**

Run: `cd backend && .venv/Scripts/python -m pytest --cov --cov-report=term-missing`
Expected: `TOTAL ... ≥ 90%` and no `FAIL Required test coverage of 90% not reached`. If below 90%, the uncovered lines listed are the target: add a test for that branch (typically a loader error path), never lower `fail_under`.

- [ ] **Step 2: Make CI enforce it**

In `.github/workflows/ci.yml`, change the backend `- run: pytest` line to:
```yaml
      - run: pytest --cov --cov-report=term-missing
```

- [ ] **Step 3: Document the CLI in the README**

Append to `README.md` under "Tests":
````markdown
### Analysis pipeline (Stage 1)

Run the analysis on any CSV that matches `backend/tests/fixtures/minimal_valid.csv`'s columns:

```bash
cd backend
python scripts/generate_sample_data.py                       # writes tests/fixtures/sample_30d.csv
python -m app.pipeline.run tests/fixtures/sample_30d.csv
python -m app.pipeline.run my.csv --overrides '{"waste_multiplier": 2}'
```

All thresholds live in `backend/app/pipeline/config.py`.
````

- [ ] **Step 4: Full suite, lint, commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check . && .venv/Scripts/python -m pytest --cov`
Expected: all pass, coverage ≥ 90%.
```bash
git add .github/workflows/ci.yml README.md
git commit -m "test(pipeline): enforce 90% coverage in CI and document the CLI"
```

---

## Stage 1 exit checklist (from `docs/PLAN.md` §6)

- [ ] Golden tests pass (Task 5).
- [ ] Coverage of `app/pipeline/` ≥ 90% (Task 7).
- [ ] The owner has hand-checked one segment's waste in `sample_30d.csv` against the CLI output (Task 6 Step 5).

## Self-review notes

- Spec coverage against `docs/PLAN.md` §3: loader hard errors ✔ (missing columns, bad dates/numbers, negatives, clicks>impressions, empty, max_rows; `max_upload_mb` is enforced at the HTTP layer in Stage 3 because the loader never sees the byte size); warnings ✔ (conversions>clicks, duplicates, unknown values); normalisation + alias map + time-slot bucketing ✔; analyzer steps 1–5 ✔ incl. both benchmark modes and zero-conversion rule; optimizer `MAX_CUT_PCT` cap, reason text, `headline_waste` = max, `calculate_fee` with Decimal and cap ✔; generator with injected waste + golden tests + edge fixtures ✔; CLI ✔; coverage gate ✔.
- Type consistency: `SegmentMetrics`/`DimensionResult` field names in Task 3 match their use in Tasks 4–6; `PipelineConfig.to_dict()` round-trips through `from_overrides` (used in Task 3's `best`-mode test and Task 6's CLI print).
- Deliberate non-goal: no DB writes here — Stage 3 maps `DimensionResult` → `WasteReport`/`SegmentMetric` rows.
