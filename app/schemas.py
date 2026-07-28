from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import config
from app.repositories import SortOrder


class PriceResponse(BaseModel):
    ticker: str
    price: Decimal
    timestamp: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str
    details: list[dict[str, Any]] | dict[str, Any] | None = None


class CandleInterval(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    ONE_HOUR = "1h"
    ONE_DAY = "1d"

    @property
    def seconds(self) -> int:
        return {
            CandleInterval.ONE_MINUTE: 60,
            CandleInterval.FIVE_MINUTES: 300,
            CandleInterval.ONE_HOUR: 3600,
            CandleInterval.ONE_DAY: 86400,
        }[self]


class CandleResponse(BaseModel):
    ticker: str
    bucket_start: int
    bucket_end: int
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    average_price: Decimal
    points: int


class PriceSummaryResponse(BaseModel):
    ticker: str
    timestamp_from: int
    timestamp_to: int
    points: int
    min_price: Decimal
    max_price: Decimal
    average_price: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    start_price: Decimal
    end_price: Decimal
    trend: str


class PaginationSortQuery(BaseModel):
    limit: int = Field(50, ge=1, le=1000, description="Количество записей (1–1000)")
    offset: int = Field(0, ge=0, description="Смещение от начала")
    sorting: SortOrder = Field(SortOrder.ASC, description="Порядок сортировки")


class TickerQuery(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        if value not in config.supported_tickers_set:
            supported = ", ".join(config.supported_tickers)
            raise ValueError(f"Ticker must be one of: {supported}")
        return value


class TickerWithPaginationQuery(PaginationSortQuery, TickerQuery):
    pass


class PriceByDateQuery(TickerWithPaginationQuery):
    timestamp_from: int | None = None
    timestamp_to: int | None = None

    @field_validator("timestamp_from", "timestamp_to")
    @classmethod
    def validate_timestamp(cls, v: int | None) -> int | None:
        if v is not None:
            if v < 0 or v > 2_500_000_000:
                raise ValueError(
                    "Timestamp must be a valid UNIX timestamp "
                    "(0 <= timestamp <= 2500000000)"
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


class CandleQuery(TickerQuery):
    interval: CandleInterval = Field(
        ...,
        description="Aggregation interval: 1m, 5m, 1h, 1d",
    )
    timestamp_from: int = Field(..., ge=0, le=2_500_000_000)
    timestamp_to: int = Field(..., ge=0, le=2_500_000_000)

    @model_validator(mode="after")
    def validate_range(self) -> "CandleQuery":
        if self.timestamp_from > self.timestamp_to:
            raise ValueError(
                "timestamp_from must be less than or equal to timestamp_to"
            )
        return self


class PriceSummaryQuery(TickerQuery):
    timestamp_from: int = Field(..., ge=0, le=2_500_000_000)
    timestamp_to: int = Field(..., ge=0, le=2_500_000_000)

    @model_validator(mode="after")
    def validate_range(self) -> "PriceSummaryQuery":
        if self.timestamp_from > self.timestamp_to:
            raise ValueError(
                "timestamp_from must be less than or equal to timestamp_to"
            )
        return self
