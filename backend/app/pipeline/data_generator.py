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
                        conversions = (
                            int(rng.binomial(clicks, BASE_CVR / multiplier)) if clicks else 0
                        )
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
