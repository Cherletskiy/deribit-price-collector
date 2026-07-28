from decimal import Decimal

import httpx

from app.core.config import config
from app.core.logging_config import setup_logger
from collector.exceptions import (
    DeribitRequestError,
    DeribitResponseError,
    UnsupportedTickerError,
)
from collector.providers import HistoryRange, MarketDataProviderName

logger = setup_logger(__name__)

IndexChartRange = HistoryRange


class SyncDeribitClient:
    BASE_URL = config.DERIBIT_API_BASE_URL.rstrip("/")
    provider_name = MarketDataProviderName.DERIBIT

    def __init__(self, http_client: httpx.Client):
        self._client = http_client

    def get_index_price_time(self, ticker: str) -> tuple[Decimal, int]:
        if ticker not in config.supported_tickers_set:
            raise UnsupportedTickerError(
                "Unsupported ticker: "
                f"{ticker}. Must be one of: {list(config.supported_tickers)}"
            )

        url = f"{self.BASE_URL}/public/get_index_price"
        params = {"index_name": ticker}

        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            logger.info(
                "GET %s | ticker=%s | status=%s",
                url,
                ticker,
                response.status_code,
            )

            result = data.get("result")
            if result is None:
                raise DeribitResponseError(
                    f"Missing 'result' field in API response: {data}"
                )

            price = result.get("index_price")
            if price is None:
                raise DeribitResponseError(f"Missing 'index_price' in result: {result}")

            us_in = data.get("usIn")
            if us_in is None:
                raise DeribitResponseError(f"Missing 'usIn' in response: {data}")

            timestamp = us_in // 1_000_000
            price_decimal = Decimal(str(price))

            logger.debug(
                "Fetched price | ticker=%s | price=%s | timestamp=%s",
                ticker,
                price_decimal,
                timestamp,
            )

            return price_decimal, timestamp

        except httpx.HTTPError as exc:
            logger.error(
                "HTTP error fetching price | ticker=%s | error=%s",
                ticker,
                exc,
            )
            raise DeribitRequestError(
                f"Failed to fetch price from Deribit for {ticker}: {exc}"
            ) from exc
        except DeribitResponseError as exc:
            logger.error(
                "Response parsing error | ticker=%s | error=%s",
                ticker,
                exc,
            )
            raise

    def get_index_chart_data(
        self,
        ticker: str,
        range_name: HistoryRange,
    ) -> list[tuple[Decimal, int]]:
        if ticker not in config.supported_tickers_set:
            raise UnsupportedTickerError(
                "Unsupported ticker: "
                f"{ticker}. Must be one of: {list(config.supported_tickers)}"
            )

        url = f"{self.BASE_URL}/public/get_index_chart_data"
        params = {
            "index_name": ticker,
            "range": range_name.value,
        }

        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            logger.info(
                "GET %s | ticker=%s | range=%s | status=%s",
                url,
                ticker,
                range_name.value,
                response.status_code,
            )

            result = data.get("result")
            if result is None or not isinstance(result, list):
                raise DeribitResponseError(
                    f"Missing or invalid 'result' field in API response: {data}"
                )

            parsed_points: list[tuple[Decimal, int]] = []
            for item in result:
                if not isinstance(item, list | tuple) or len(item) != 2:
                    raise DeribitResponseError(
                        f"Invalid chart data point in API response: {item}"
                    )

                timestamp_ms, price = item
                if not isinstance(timestamp_ms, int | float):
                    raise DeribitResponseError(
                        f"Invalid chart data timestamp in API response: {item}"
                    )

                parsed_points.append(
                    (
                        Decimal(str(price)),
                        int(timestamp_ms) // 1000,
                    )
                )

            return parsed_points

        except httpx.HTTPError as exc:
            logger.error(
                "HTTP error fetching chart data | ticker=%s | range=%s | error=%s",
                ticker,
                range_name.value,
                exc,
            )
            raise DeribitRequestError(
                "Failed to fetch chart data from Deribit "
                f"for {ticker} with range {range_name.value}: {exc}"
            ) from exc
        except DeribitResponseError as exc:
            logger.error(
                "Chart response parsing error | ticker=%s | range=%s | error=%s",
                ticker,
                range_name.value,
                exc,
            )
            raise
