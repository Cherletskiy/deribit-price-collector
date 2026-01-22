from decimal import Decimal

import requests

from app.core.config import config
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class SyncDeribitClient:
    """
    Синхронный клиент для Deribit API.
    Поддерживает получение index price для BTC и ETH.
    """

    BASE_URL = config.DERIBIT_API_BASE_URL.rstrip("/")

    def get_index_price_time(self, ticker: str) -> tuple[Decimal, int]:
        """
        Получает текущую индексную цену для указанного тикера.

        Args:
            ticker (Literal["btc_usd", "eth_usd"]): тикер валюты

        Returns:
            Tuple[Decimal, int]: (price, timestamp)

        Raises:
            ValueError: если тикер не поддерживается или ответ некорректный
            requests.RequestException: ошибки сети
        """
        if ticker not in ["btc_usd", "eth_usd"]:
            raise ValueError(f"Unsupported ticker: {ticker}")

        url = f"{self.BASE_URL}/public/get_index_price"
        params = {"index_name": ticker}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info(
                f"GET {self.BASE_URL}/public/get_index_price | ticker: {ticker} | status: {response.status_code}"
            )

            result = data.get("result")
            if result is None:
                raise ValueError(
                    f"Unexpected response format: missing 'result' in {data}"
                )

            price = result.get("index_price")
            if price is None:
                raise ValueError(f"Missing 'index_price' in result: {result}")

            us_in = data.get("usIn")
            if us_in is None:
                raise ValueError(f"Missing 'usIn' in response: {data}")

            # Конвертируем микросекунды в секунды
            timestamp = us_in // 1_000_000

            price_decimal = Decimal(str(price))

            return price_decimal, timestamp

        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error(f"Failed to fetch index price for {ticker}: {e}")
            raise
