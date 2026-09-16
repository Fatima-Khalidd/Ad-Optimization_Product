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


# Columns whose values are aliased/collapsed via _normalise_category + CATEGORY_ALIASES.
# campaign_id and age_group are shown to clients verbatim (or near-verbatim) and must not
# have hyphens collapsed or (for campaign_id) be lowercased.
_ALIASED_CATEGORY_COLUMNS = ("placement", "gender", "device", "time_slot")


def _normalise_campaign_id(value: str) -> str:
    return value.strip()


def _normalise_age_group(value: str) -> str:
    return value.strip().lower()


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
        warnings.append(
            RowIssue(int(r), "conversions", "conversions exceed clicks (view-through?)")
        )

    # --- categories ---
    for col in CATEGORY_COLUMNS:
        if col == "campaign_id":
            values = df[col].map(_normalise_campaign_id)
        elif col == "age_group":
            values = df[col].map(_normalise_age_group)
        else:
            values = df[col].map(_normalise_category)
        aliases = CATEGORY_ALIASES.get(col, {}) if col in _ALIASED_CATEGORY_COLUMNS else {}
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
