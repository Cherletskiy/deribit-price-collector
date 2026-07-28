from decimal import Decimal

import httpx

from app.core.config import config
from app.core.logging_config import setup_logger
from collector.exceptions import (
    DeribitRequestError,
    DeribitResponseError,
    UnsupportedTickerError,
)

logger = setup_logger(__name__)


class SyncDeribitClient:
    BASE_URL = config.DERIBIT_API_BASE_URL.rstrip("/")

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
