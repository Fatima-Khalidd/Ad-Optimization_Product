"""Request and response models for /api/admin. Decimals serialize as JSON strings."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClientPatch(BaseModel):
    """A partial client update. Only the fields actually sent are applied."""

    model_config = ConfigDict(extra="forbid")

    base_fee: Decimal | None = Field(default=None, ge=0)
    performance_fee_pct: Decimal | None = Field(default=None, ge=0, le=100)
    config_overrides: dict[str, Any] | None = None
