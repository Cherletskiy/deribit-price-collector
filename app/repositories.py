from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Price


class AsyncPriceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_price(self, ticker: str, price: Decimal, timestamp: int) -> Price:
        price_obj = Price(ticker=ticker, price=price, timestamp=timestamp)
        self.session.add(price_obj)
        return price_obj

    async def get_all_by_ticker(self, ticker: str):
        stmt = select(Price).where(Price.ticker == ticker).order_by(Price.timestamp.asc())
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_latest_by_ticker(self, ticker: str):
        stmt = select(Price).where(Price.ticker == ticker).order_by(Price.timestamp.desc()).limit(1)
        result = await self.session.scalars(stmt)
        return result.first()

    async def get_by_ticker_and_date_range(self, ticker: str, timestamp_from: int | None, timestamp_to: int | None):
        stmt = select(Price).where(Price.ticker == ticker)
        if timestamp_from is not None:
            stmt = stmt.where(Price.timestamp >= timestamp_from)
        if timestamp_to is not None:
            stmt = stmt.where(Price.timestamp <= timestamp_to)
        stmt = stmt.order_by(Price.timestamp.asc())
        result = await self.session.scalars(stmt)
        return list(result.all())
