"""Every tunable number in the analysis lives here. Nothing else hardcodes a threshold."""

from dataclasses import asdict, dataclass, fields
from decimal import Decimal, InvalidOperation
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
_FLOAT_FIELDS = {"min_spend", "min_spend_zero_conv", "waste_multiplier", "max_cut_pct"}
_INT_FIELDS = {"min_clicks", "min_conversions_for_best", "max_upload_mb", "max_rows"}


def _coerce_float(key: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a number, got {value!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number, got {value!r}") from exc


def _coerce_int(key: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a whole number, got {value!r}")
    if isinstance(value, int):
        return value
    try:
        as_float = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a whole number, got {value!r}") from exc
    if not as_float.is_integer():
        raise ValueError(f"{key} must be a whole number, got {value!r}")
    return int(as_float)


def _coerce_decimal(key: str, value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a number, got {value!r}")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{key} must be a number, got {value!r}") from exc


@dataclass(frozen=True)
class PipelineConfig:
    # --- significance: segments below these are shown but never flagged ---
    min_spend: float = 5000.0
    min_clicks: int = 100
    # --- flagging ---
    benchmark_mode: BenchmarkMode = "account_avg"
    waste_multiplier: float = 1.5
    # gated by significance — only effective when >= min_spend, since non-significant
    # segments are never flagged
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
            if key in _FLOAT_FIELDS:
                value = _coerce_float(key, value)
            elif key in _INT_FIELDS:
                value = _coerce_int(key, value)
            elif key in _DECIMAL_FIELDS and value is not None:
                value = _coerce_decimal(key, value)
            values[key] = value
        cfg = cls(**values)

        if cfg.benchmark_mode not in ("account_avg", "best"):
            raise ValueError(
                f"benchmark_mode must be 'account_avg' or 'best', got {cfg.benchmark_mode!r}"
            )
        if cfg.min_spend < 0:
            raise ValueError(f"min_spend must be >= 0, got {cfg.min_spend!r}")
        if cfg.min_spend_zero_conv < 0:
            raise ValueError(f"min_spend_zero_conv must be >= 0, got {cfg.min_spend_zero_conv!r}")
        if cfg.waste_multiplier <= 1:
            raise ValueError(f"waste_multiplier must be > 1, got {cfg.waste_multiplier!r}")
        if not (0 < cfg.max_cut_pct <= 1):
            raise ValueError(f"max_cut_pct must be in (0, 1], got {cfg.max_cut_pct!r}")
        if cfg.min_clicks < 0:
            raise ValueError(f"min_clicks must be >= 0, got {cfg.min_clicks!r}")
        if cfg.min_conversions_for_best < 0:
            raise ValueError(
                f"min_conversions_for_best must be >= 0, got {cfg.min_conversions_for_best!r}"
            )
        if cfg.max_upload_mb < 1:
            raise ValueError(f"max_upload_mb must be >= 1, got {cfg.max_upload_mb!r}")
        if cfg.max_rows < 1:
            raise ValueError(f"max_rows must be >= 1, got {cfg.max_rows!r}")
        if cfg.base_fee < 0:
            raise ValueError(f"base_fee must be >= 0, got {cfg.base_fee!r}")
        if not (Decimal("0") <= cfg.performance_fee_pct <= Decimal("100")):
            raise ValueError(
                f"performance_fee_pct must be between 0 and 100, got {cfg.performance_fee_pct!r}"
            )
        if cfg.performance_fee_cap is not None and cfg.performance_fee_cap < 0:
            raise ValueError(
                f"performance_fee_cap must be >= 0 or None, got {cfg.performance_fee_cap!r}"
            )
        return cfg

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in _DECIMAL_FIELDS:
            if data[key] is not None:
                data[key] = str(data[key])
        return data
