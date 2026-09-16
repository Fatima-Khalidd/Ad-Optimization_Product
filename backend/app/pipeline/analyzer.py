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
    # Zero-conversion segments contribute spend with nothing to divide it by, which would
    # inflate the benchmark and could un-flag a genuinely wasteful segment. Exclude them.
    converting = sig[sig["conversions"] > 0]
    total_conv = converting["conversions"].sum()
    if total_conv == 0:
        return None
    return float(converting["spend"].sum() / total_conv)


def analyze_dimension(df: pd.DataFrame, dimension: str, config: PipelineConfig) -> DimensionResult:
    rows = df[df[dimension].fillna("").astype(str) != ""]
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
        total_wasted_spend=sum((s.wasted_spend for s in segments), 0.0),
        segments=segments,
    )


def analyze_all_dimensions(df: pd.DataFrame, config: PipelineConfig) -> dict[str, DimensionResult]:
    return {dim: analyze_dimension(df, dim, config) for dim in DIMENSIONS}


def account_total_spend(df: pd.DataFrame) -> float:
    """Total spend across every loaded row, regardless of which dimensions are populated."""
    if df.empty:
        return 0.0
    return float(df["spend"].sum())
