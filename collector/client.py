import aiohttp
from decimal import Decimal
from typing import Optional, Literal

from app.core.config import Config
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class DeribitClient:
    """
    Асинхронный клиент для Deribit API.
    Поддерживает получение index price для BTC и ETH.
    """

    BASE_URL = Config.DERIBIT_API_BASE_URL

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_index_price_time(self, ticker: Literal["btc_usd", "eth_usd"]) -> tuple[Decimal, int]:
        """
        Получает текущую индексную цену для указанного тикера.

        Args:
            ticker (Literal["btc_usd", "eth_usd"]): тикер валюты

        Returns:
            Decimal: цена

        Raises:
            ValueError: если тикер не поддерживается
            RuntimeError: если session не инициализирована
            aiohttp.ClientError: ошибки сети
        """
        if ticker not in ["btc_usd", "eth_usd"]:
            raise ValueError(f"Unsupported ticker: {ticker}")

        if not self._session:
            raise RuntimeError(
                "Client session not initialized. Use async with DeribitClient()."
            )

        # формируем API URL и параметры
        url = f"{self.BASE_URL}/public/get_index_price"
        params = {"index_name": ticker}

        try:
            async with self._session.get(url, params=params) as resp:
                resp.raise_for_status()
                data = await resp.json()

            result = data.get("result")
            if result is None:
                raise ValueError(f"Unexpected response format: missing 'result' in {data}")

            price = result.get("index_price")
            if price is None:
                raise ValueError(f"Missing 'index_price' in result: {result}")

            us_in = result.get("usIn")
            timestamp = int(us_in / 1_000_000)

            price_decimal = Decimal(str(price))
            logger.debug(f"Fetched index price for {ticker}: {price_decimal}")
            return price_decimal, timestamp

        except (aiohttp.ClientError, ValueError, KeyError) as e:
            logger.error(f"Failed to fetch index price for {ticker}: {e}")
            raise
