from decimal import Decimal
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models import Price


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class AsyncPriceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_by_ticker(
        self,
        ticker: str,
        limit: int = 50,
        offset: int = 0,
        sorting: SortOrder = SortOrder.ASC,
    ):
        order = (
            Price.timestamp.desc()
            if sorting is SortOrder.DESC
            else Price.timestamp.asc()
        )

        stmt = (
            select(Price)
            .where(Price.ticker == ticker)
            .order_by(order)
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_latest_by_ticker(self, ticker: str):
        stmt = (
            select(Price)
            .where(Price.ticker == ticker)
            .order_by(Price.timestamp.desc())
            .limit(1)
        )

        result = await self.session.scalars(stmt)
        return result.first()

    async def get_by_ticker_and_date_range(
        self,
        ticker: str,
        timestamp_from: int | None,
        timestamp_to: int | None,
        limit: int = 50,
        offset: int = 0,
        sorting: SortOrder = SortOrder.ASC,
    ):
        stmt = select(Price).where(Price.ticker == ticker)

        if timestamp_from is not None:
            stmt = stmt.where(Price.timestamp >= timestamp_from)
        if timestamp_to is not None:
            stmt = stmt.where(Price.timestamp <= timestamp_to)

        order = (
            Price.timestamp.desc()
            if sorting is SortOrder.DESC
            else Price.timestamp.asc()
        )

        stmt = stmt.order_by(order).limit(limit).offset(offset)

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_total_prices_count(self) -> int:
        stmt = select(func.count(Price.id))
        result = await self.session.scalar(stmt)
        return int(result or 0)

    async def get_counts_by_ticker(self) -> dict[str, int]:
        stmt = select(Price.ticker, func.count(Price.id)).group_by(Price.ticker)
        result = await self.session.execute(stmt)
        return {ticker: int(count) for ticker, count in result.all()}

    async def get_latest_prices_by_ticker(self) -> dict[str, Price]:
        latest_timestamp_subquery = (
            select(
                Price.ticker.label("ticker"),
                func.max(Price.timestamp).label("latest_timestamp"),
            )
            .group_by(Price.ticker)
            .subquery()
        )

        stmt = (
            select(Price)
            .join(
                latest_timestamp_subquery,
                (Price.ticker == latest_timestamp_subquery.c.ticker)
                & (Price.timestamp == latest_timestamp_subquery.c.latest_timestamp),
            )
            .order_by(Price.ticker.asc())
        )

        result = await self.session.scalars(stmt)
        latest_prices = list(result.all())
        return {price.ticker: price for price in latest_prices}


class SyncPriceRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_price(self, ticker: str, price: Decimal, timestamp: int) -> Price:
        stmt = select(Price).where(
            Price.ticker == ticker,
            Price.timestamp == timestamp,
        )
        obj = self.session.execute(stmt).scalar_one_or_none()

        if obj is None:
            obj = Price(ticker=ticker, price=price, timestamp=timestamp)
            self.session.add(obj)
            return obj

        obj.price = price
        return obj

    def get_latest_timestamp(self, ticker: str) -> int | None:
        stmt = (
            select(Price.timestamp)
            .where(Price.ticker == ticker)
            .order_by(Price.timestamp.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_timestamps_in_range(
        self,
        ticker: str,
        timestamp_from: int,
        timestamp_to: int,
    ) -> list[int]:
        stmt = (
            select(Price.timestamp)
            .where(
                Price.ticker == ticker,
                Price.timestamp >= timestamp_from,
                Price.timestamp <= timestamp_to,
            )
            .order_by(Price.timestamp.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
