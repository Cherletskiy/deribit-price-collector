from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

import httpx

from app.core.config import config


class MarketDataProviderName(StrEnum):
    DERIBIT = "deribit"


class HistoryRange(StrEnum):
    ONE_HOUR = "1h"
    ONE_DAY = "1d"
    TWO_DAYS = "2d"
    ONE_MONTH = "1m"
    ONE_YEAR = "1y"
    ALL = "all"


@dataclass(frozen=True)
class ProviderInstrument:
    ticker: str
    provider: MarketDataProviderName


@dataclass(frozen=True)
class ProviderMetadata:
    name: MarketDataProviderName
    display_name: str
    base_url: str
    supported_tickers: tuple[str, ...]
    supports_backfill: bool


class SyncMarketDataProvider(Protocol):
    provider_name: MarketDataProviderName

    def get_index_price_time(self, ticker: str) -> tuple[Decimal, int]:
        pass

    def get_index_chart_data(
        self,
        ticker: str,
        range_name: HistoryRange,
    ) -> list[tuple[Decimal, int]]:
        pass


def build_sync_market_data_provider(
    http_client: httpx.Client,
) -> SyncMarketDataProvider:
    if config.MARKET_DATA_PROVIDER == MarketDataProviderName.DERIBIT:
        from collector.client import SyncDeribitClient

        return SyncDeribitClient(http_client)
    raise ValueError(f"Unsupported market data provider: {config.MARKET_DATA_PROVIDER}")


def list_provider_metadata() -> list[ProviderMetadata]:
    return [
        ProviderMetadata(
            name=MarketDataProviderName.DERIBIT,
            display_name="Deribit",
            base_url=config.DERIBIT_API_BASE_URL.rstrip("/"),
            supported_tickers=config.supported_tickers,
            supports_backfill=True,
        )
    ]


def get_active_provider_metadata() -> ProviderMetadata:
    active_name = MarketDataProviderName(config.MARKET_DATA_PROVIDER)
    for provider in list_provider_metadata():
        if provider.name == active_name:
            return provider
    raise ValueError(f"Unsupported market data provider: {active_name}")


def list_supported_instruments() -> list[ProviderInstrument]:
    active_provider = get_active_provider_metadata()
    return [
        ProviderInstrument(ticker=ticker, provider=active_provider.name)
        for ticker in active_provider.supported_tickers
    ]


def supported_tickers() -> Sequence[str]:
    return tuple(instrument.ticker for instrument in list_supported_instruments())
