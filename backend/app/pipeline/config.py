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
            raise ValueError(
                f"benchmark_mode must be 'account_avg' or 'best', got {cfg.benchmark_mode!r}"
            )
        return cfg

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in _DECIMAL_FIELDS:
            if data[key] is not None:
                data[key] = str(data[key])
        return data
