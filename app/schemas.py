from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class PriceResponse(BaseModel):
    ticker: str
    price: Decimal
    timestamp: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )


class TickerQuery(BaseModel):
    """Базовая схема для запросов с тикером"""

    ticker: Literal["btc_usd", "eth_usd"]


class PriceByDateQuery(TickerQuery):
    timestamp_from: int | None = None
    timestamp_to: int | None = None

    @field_validator("timestamp_from", "timestamp_to")
    @classmethod
    def validate_timestamp(cls, v: int | None) -> int | None:
        if v is not None:
            if v < 0 or v > 2_500_000_000:
                raise ValueError(
                    "Timestamp must be a valid UNIX timestamp (0 <= timestamp <= 2500000000)"
                )
        return v

    @model_validator(mode="after")
    def validate_range(self) -> "PriceByDateQuery":
        if self.timestamp_from is not None and self.timestamp_to is not None:
            if self.timestamp_from > self.timestamp_to:
                raise ValueError(
                    "timestamp_from must be less than or equal to timestamp_to"
                )
        return self
