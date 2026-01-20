from app.models import Price
from app.repositories import AsyncPriceRepository, SortOrder


class PriceService:
    """
    Сервис для работы с ценами валют.
    Используется в FastAPI endpoints.
    """

    def __init__(self, repo: AsyncPriceRepository):
        self.repo = repo

    async def get_all_prices(
        self,
        ticker: str,
        limit: int = 50,
        offset: int = 0,
        sorting: SortOrder = SortOrder.ASC,
    ) -> list[Price]:
        """
        Возвращает все цены по тикеру используя репо.
        """
        return await self.repo.get_all_by_ticker(
            ticker=ticker, limit=limit, offset=offset, sorting=sorting
        )

    async def get_latest_price(self, ticker: str) -> Price | None:
        """
        Возвращает последнюю цену по тикеру.
        """
        return await self.repo.get_latest_by_ticker(ticker)

    async def get_prices_by_date_range(
        self,
        ticker: str,
        timestamp_from: int | None = None,
        timestamp_to: int | None = None,
        limit: int = 50,
        offset: int = 0,
        sorting: SortOrder = SortOrder.ASC,
    ) -> list[Price]:
        """
        Возвращает цены по тикеру с фильтром по временному диапазону (UNIX timestamp).
        """
        return await self.repo.get_by_ticker_and_date_range(
            ticker=ticker,
            timestamp_from=timestamp_from,
            timestamp_to=timestamp_to,
            limit=limit,
            offset=offset,
            sorting=sorting,
        )
