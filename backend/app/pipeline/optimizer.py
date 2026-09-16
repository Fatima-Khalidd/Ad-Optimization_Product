"""Turn flagged segments into capped budget cuts, and compute the hybrid fee with Decimal."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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


def _as_decimal(value: Decimal | int | float | str) -> Decimal:
    """Coerce API-facing numeric inputs to Decimal without going through binary float."""
    if isinstance(value, Decimal):
        result = value
    else:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f"not a number: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"not a finite number: {value!r}")
    return result


def calculate_fee(
    base_fee: Decimal | int | float | str,
    performance_fee_pct: Decimal | int | float | str,
    confirmed_recovered_waste: Decimal | int | float | str,
    cap: Decimal | int | float | str | None = None,
) -> FeeBreakdown:
    base_fee = _as_decimal(base_fee)
    performance_fee_pct = _as_decimal(performance_fee_pct)
    confirmed_recovered_waste = _as_decimal(confirmed_recovered_waste)
    cap = _as_decimal(cap) if cap is not None else None

    if base_fee < 0 or confirmed_recovered_waste < 0:
        raise ValueError("base_fee and confirmed_recovered_waste must be >= 0")
    if not (Decimal("0") <= performance_fee_pct <= Decimal("100")):
        raise ValueError("performance_fee_pct must be between 0 and 100")
    if cap is not None and cap < 0:
        raise ValueError("cap must be >= 0")

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
