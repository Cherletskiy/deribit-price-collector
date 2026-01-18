from decimal import Decimal
from typing import List, Optional

from app.models import Price
from app.repositories import AsyncPriceRepository


class PriceService:
    """
    Сервис для работы с ценами валют.
    Используется в FastAPI endpoints.
    """

    def __init__(self, repo: AsyncPriceRepository):
        self.repo = repo

    async def get_all_prices(self, ticker: str) -> List[Price]:
        """
        Возвращает все цены по тикеру.
        """
        return await self.repo.get_all_by_ticker(ticker)

    async def get_latest_price(self, ticker: str) -> Optional[Price]:
        """
        Возвращает последнюю цену по тикеру.
        """
        return await self.repo.get_latest_by_ticker(ticker)

    async def get_prices_by_date_range(
        self,
        ticker: str,
        timestamp_from: Optional[int] = None,
        timestamp_to: Optional[int] = None,
    ) -> List[Price]:
        """
        Возвращает цены по тикеру с фильтром по временному диапазону (UNIX timestamp).
        """
        return await self.repo.get_by_ticker_and_date_range(
            ticker=ticker,
            timestamp_from=timestamp_from,
            timestamp_to=timestamp_to,
        )
