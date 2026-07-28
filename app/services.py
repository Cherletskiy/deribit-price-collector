from collections import defaultdict
from decimal import Decimal

from app.models import Price
from app.repositories import AsyncPriceRepository, SortOrder
from app.schemas import (
    CandleInterval,
    CandleResponse,
    PriceSummaryResponse,
)


class PriceService:
    def __init__(self, repo: AsyncPriceRepository):
        self.repo = repo

    async def get_all_prices(
        self,
        ticker: str,
        limit: int = 50,
        offset: int = 0,
        sorting: SortOrder = SortOrder.ASC,
    ) -> list[Price]:
        return await self.repo.get_all_by_ticker(
            ticker=ticker, limit=limit, offset=offset, sorting=sorting
        )

    async def get_latest_price(self, ticker: str) -> Price | None:
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
        return await self.repo.get_by_ticker_and_date_range(
            ticker=ticker,
            timestamp_from=timestamp_from,
            timestamp_to=timestamp_to,
            limit=limit,
            offset=offset,
            sorting=sorting,
        )

    async def get_candles(
        self,
        ticker: str,
        interval: CandleInterval,
        timestamp_from: int,
        timestamp_to: int,
    ) -> list[CandleResponse]:
        prices = await self.repo.get_by_ticker_and_date_range(
            ticker=ticker,
            timestamp_from=timestamp_from,
            timestamp_to=timestamp_to,
            limit=10_000,
            offset=0,
            sorting=SortOrder.ASC,
        )

        buckets: dict[int, list[Price]] = defaultdict(list)
        interval_seconds = interval.seconds

        for price in prices:
            bucket_start = (price.timestamp // interval_seconds) * interval_seconds
            buckets[bucket_start].append(price)

        candles: list[CandleResponse] = []
        for bucket_start in sorted(buckets):
            bucket_prices = buckets[bucket_start]
            price_values = [entry.price for entry in bucket_prices]
            average_price = sum(price_values, Decimal("0")) / Decimal(
                len(bucket_prices)
            )

            candles.append(
                CandleResponse(
                    ticker=ticker,
                    bucket_start=bucket_start,
                    bucket_end=bucket_start + interval_seconds - 1,
                    open_price=bucket_prices[0].price,
                    high_price=max(price_values),
                    low_price=min(price_values),
                    close_price=bucket_prices[-1].price,
                    average_price=average_price,
                    points=len(bucket_prices),
                )
            )

        return candles

    async def get_price_summary(
        self,
        ticker: str,
        timestamp_from: int,
        timestamp_to: int,
    ) -> PriceSummaryResponse | None:
        prices = await self.repo.get_by_ticker_and_date_range(
            ticker=ticker,
            timestamp_from=timestamp_from,
            timestamp_to=timestamp_to,
            limit=10_000,
            offset=0,
            sorting=SortOrder.ASC,
        )

        if not prices:
            return None

        price_values = [entry.price for entry in prices]
        start_price = prices[0].price
        end_price = prices[-1].price
        price_change = end_price - start_price

        if start_price == Decimal("0"):
            price_change_percent = Decimal("0")
        else:
            price_change_percent = (price_change / start_price) * Decimal("100")

        if price_change > 0:
            trend = "up"
        elif price_change < 0:
            trend = "down"
        else:
            trend = "flat"

        average_price = sum(price_values, Decimal("0")) / Decimal(len(prices))

        return PriceSummaryResponse(
            ticker=ticker,
            timestamp_from=timestamp_from,
            timestamp_to=timestamp_to,
            points=len(prices),
            min_price=min(price_values),
            max_price=max(price_values),
            average_price=average_price,
            price_change=price_change,
            price_change_percent=price_change_percent,
            start_price=start_price,
            end_price=end_price,
            trend=trend,
        )
